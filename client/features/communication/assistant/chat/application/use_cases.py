"""Use cases del assistant (REST + stream de eventos)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Iterator, Optional

from core.ai.assistant_policy import AssistantRuntimePolicy, default_assistant_policy
from core.ai.model_layer import resolve_chat_model
from core.ai.assistant_status import (
    ASSISTANT_STATUS_COMPOSING,
    ASSISTANT_STATUS_INTERPRETING,
    status_payload,
)
from core.ai.harness.cancel import RunCancelStore
from core.ai.harness.environment import CapabilityBoundary
from core.errors import (
    AppErrorCode,
    NotFoundException,
    ServerException,
    ValidationAppException,
)
from core.ids import uuid7


from client.features.communication.assistant.chat.application.agent import AssistantAgent, chunk_text
from client.features.communication.assistant.chat.application.message import normalize_chat_message
from client.features.communication.assistant.chat.application.ui_context import normalize_ui_context
from client.features.communication.assistant.chat.domain.interfaces import IAssistantConversationRepository
from client.features.communication.assistant.chat.domain.run_interfaces import IAssistantAgentRunRepository
from client.features.communication.assistant.chat.domain.schemas import (
    AssistantStatusSchema,
    ChatTurnResultSchema,
    ConversationSummarySchema,
)
from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry
from client.features.communication.assistant.credentials.domain.interfaces import (
    IAssistantCredentialRepository,
)
from core.trace import trace_layer

logger = logging.getLogger('app.ai')


def _wire_event(type_: str, payload: dict | None = None) -> dict:
    return {
        'type': type_,
        'payload': payload or {},
        'ts': datetime.now(timezone.utc).isoformat(),
    }


class GetAssistantStatusUseCase:
    def __init__(self, policy: AssistantRuntimePolicy | None = None):
        self.policy = policy or default_assistant_policy()

    @trace_layer('application')
    def execute(self) -> AssistantStatusSchema:
        return AssistantStatusSchema(
            enabled=self.policy.chat_allowed,
            provider=self.policy.provider,
        )


class ChatTurnUseCase:
    def __init__(
        self,
        repository: IAssistantConversationRepository,
        registry: ToolRegistry,
        *,
        model=None,
        policy: AssistantRuntimePolicy | None = None,
        run_repository: IAssistantAgentRunRepository | None = None,
        credential_repository: IAssistantCredentialRepository | None = None,
        tenant_schema: str = '',
        actor_user_id: uuid.UUID | None = None,
    ):
        self.repository = repository
        self.registry = registry
        self._model = model
        self.policy = policy or default_assistant_policy()
        self._ui_context: dict[str, str] = {}
        self.run_repository = run_repository
        self.credential_repository = credential_repository
        self._tenant_schema = tenant_schema
        self._actor_user_id = actor_user_id
        self._cancel_event: threading.Event | None = None
        self._run_id: uuid.UUID | None = None

    def set_ui_context(self, ui_context: Optional[dict] = None) -> None:
        self._ui_context = normalize_ui_context(ui_context)

    def bind_cancel(
        self,
        *,
        run_id: uuid.UUID | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self._run_id = run_id
        self._cancel_event = cancel_event

    @trace_layer('application')
    def execute(
        self,
        *,
        user_id: uuid.UUID,
        message: str,
        conversation_id: Optional[uuid.UUID] = None,
        ui_context: Optional[dict] = None,
    ) -> ChatTurnResultSchema:
        text = normalize_chat_message(self.policy, message)
        self.set_ui_context(ui_context)
        conv_id, history, pending_title, pending_create = self.prepare(
            user_id, text, conversation_id,
        )
        model = self._resolve_model()
        run_id = self._run_id or uuid7()
        self._start_run(
            run_id=run_id,
            user_id=user_id,
            conversation_id=None if pending_create else conv_id,
            model=model,
        )
        agent = self.build_agent(model, run_id=run_id)
        try:
            reply, audits, degraded, cancelled = agent.run(text, history=history)
            if cancelled and pending_create:
                self._finish_run(
                    run_id,
                    status='cancelled',
                    degraded=degraded,
                    step_count=len(audits),
                    cancel_requested=True,
                )
                return ChatTurnResultSchema(
                    conversation_id=conv_id,
                    reply=reply,
                    degraded=degraded,
                    tools_used=audits,
                    messages=[],
                )
            result = self.persist(
                conv_id,
                user_id=user_id,
                user_text=text,
                reply=reply,
                audits=audits,
                degraded=degraded,
                pending_title=pending_title,
                pending_create=pending_create,
            )
            self._finish_run(
                run_id,
                status='cancelled' if cancelled else ('degraded' if degraded else 'completed'),
                conversation_id=result.conversation_id,
                degraded=degraded,
                step_count=len(audits),
                cancel_requested=cancelled,
            )
            return result
        except Exception as exc:
            code = getattr(getattr(exc, 'code', None), 'value', None) or type(exc).__name__
            self._finish_run(
                run_id,
                status='failed',
                conversation_id=None if pending_create else conv_id,
                error_code=str(code)[:40],
            )
            raise

    def _resolve_model(self):
        if self._model is not None:
            return self._model
        from platform.features.configuration.ai.model_routing.infrastructure.repositories import (
            load_routing_table,
        )
        table = load_routing_table()
        preferred = self.policy.provider
        api_key = None
        api_key_provider = None
        if self.credential_repository is not None:
            try:
                from client.features.communication.assistant.credentials.application.use_cases import (
                    ResolveActiveByokUseCase,
                )
                # Prefer BYOK for the policy/route provider only (no ambiguous pick).
                byok = ResolveActiveByokUseCase(self.credential_repository).execute(preferred)
                if byok is not None:
                    preferred = byok.provider
                    api_key = byok.api_key
                    api_key_provider = byok.provider
            except Exception as exc:
                logger.info('BYOK resolve skipped: %s', exc)
        model, _route = resolve_chat_model(
            'chat',
            preferred_provider=preferred,
            table=table,
            api_key=api_key,
            api_key_provider=api_key_provider,
        )
        return model

    def build_agent(self, model, *, run_id: uuid.UUID | None = None) -> AssistantAgent:
        rid = run_id or self._run_id
        cancel_store = RunCancelStore(
            schema=self._tenant_schema,
            user_id=self._actor_user_id,
        )
        from core.ai.harness.approval import RunApprovalStore
        approval_store = RunApprovalStore(
            schema=self._tenant_schema,
            user_id=self._actor_user_id,
        )
        agent = AssistantAgent(
            model,
            self.registry,
            max_steps=self.policy.max_agent_steps,
            history_turns=self.policy.history_turns,
            out_of_scope_message=self.policy.out_of_scope_text,
            require_tool_before_facts=self.policy.require_tool_before_facts,
            ui_context=self._ui_context,
            run_id=rid,
            cancel_event=self._cancel_event,
            cancel_store=cancel_store,
            approval_store=approval_store,
            capability=CapabilityBoundary(self.registry.names()),
        )
        if self.run_repository is not None:
            agent.on_awaiting_approval = self.run_repository.mark_awaiting_approval
        return agent

    def _start_run(self, *, run_id, user_id, conversation_id, model) -> None:
        if self.run_repository is None:
            return
        try:
            self.run_repository.start(
                user_id=user_id,
                run_id=run_id,
                conversation_id=conversation_id,
                provider=getattr(model, 'provider_name', '') or self.policy.provider,
                model_id=getattr(model, 'model_name', '') or '',
            )
        except Exception as exc:
            logger.warning('agent run start persist failed: %s', exc)

    def _finish_run(
        self,
        run_id: uuid.UUID,
        *,
        status: str,
        conversation_id=None,
        degraded: bool = False,
        step_count: int = 0,
        error_code: str = '',
        cancel_requested: bool = False,
    ) -> None:
        if self.run_repository is None:
            return
        try:
            self.run_repository.finish(
                run_id,
                status=status,  # type: ignore[arg-type]
                conversation_id=conversation_id,
                degraded=degraded,
                step_count=step_count,
                error_code=error_code,
                cancel_requested=cancel_requested,
            )
            if cancel_requested:
                RunCancelStore(
                    schema=self._tenant_schema,
                    user_id=self._actor_user_id,
                ).clear(run_id)
        except Exception as exc:
            logger.warning('agent run finish persist failed: %s', exc)

    @trace_layer('application')
    def prepare(
        self,
        user_id: uuid.UUID,
        text: str,
        conversation_id: Optional[uuid.UUID],
    ) -> tuple[uuid.UUID, list[dict[str, str]], Optional[str], bool]:
        """
        Resuelve conversación e historial sin persistir el mensaje de usuario.

        Conversaciones nuevas reciben un uuid7 en memoria; la fila se crea en
        ``persist`` para no dejar shells vacíos si el agente falla.
        """
        if conversation_id is not None:
            if not self.repository.ensure_owned(conversation_id, user_id):
                raise NotFoundException(AppErrorCode.AI_CONVERSATION_NOT_FOUND)
            history_rows = self.repository.list_messages(
                conversation_id, limit=self.policy.history_turns,
            )
            history = [
                {'role': m.role, 'content': m.content}
                for m in history_rows
                if m.role in ('user', 'assistant')
            ]
            return conversation_id, history, None, False

        return uuid7(), [], text, True

    @trace_layer('application')
    def persist(
        self,
        conv_id,
        *,
        user_id: uuid.UUID,
        user_text: str,
        reply: str,
        audits,
        degraded: bool,
        pending_title: Optional[str] = None,
        pending_create: bool = False,
    ) -> ChatTurnResultSchema:
        if pending_create:
            self.repository.create(user_id=user_id, conversation_id=conv_id)
        tool_audits = [
            {
                'tool_name': audit.tool_name,
                'arguments': audit.arguments,
                'result_preview': audit.result_preview,
                'success': audit.success,
                'error_code': audit.error_code,
            }
            for audit in audits
        ]
        self.repository.save_turn(
            conv_id,
            user_text=user_text,
            reply=reply,
            tool_audits=tool_audits,
            pending_title=pending_title,
        )
        messages = self.repository.list_messages(conv_id, limit=40)
        return ChatTurnResultSchema(
            conversation_id=conv_id,
            reply=reply,
            degraded=degraded,
            tools_used=audits,
            messages=messages,
        )


class ChatTurnStreamUseCase:
    """
    Misma lógica que ChatTurnUseCase, pero emite sobres wire para WebSocket:

    ``assistant.status`` → ``assistant.tool``* → ``assistant.typing`` →
    ``assistant.token``* → ``assistant.done`` | ``assistant.cancelled`` | ``assistant.error``
    """

    def __init__(
        self,
        repository: IAssistantConversationRepository,
        registry: ToolRegistry,
        *,
        model=None,
        policy: AssistantRuntimePolicy | None = None,
        run_repository: IAssistantAgentRunRepository | None = None,
        credential_repository: IAssistantCredentialRepository | None = None,
        cancel_event: threading.Event | None = None,
        run_id: uuid.UUID | None = None,
        tenant_schema: str = '',
        actor_user_id: uuid.UUID | None = None,
    ):
        self._turn = ChatTurnUseCase(
            repository,
            registry,
            model=model,
            policy=policy,
            run_repository=run_repository,
            credential_repository=credential_repository,
            tenant_schema=tenant_schema,
            actor_user_id=actor_user_id,
        )
        self.repository = repository
        self.registry = registry
        self._model = model
        self.policy = policy or default_assistant_policy()
        self._cancel_event = cancel_event
        self._run_id = run_id

    @trace_layer('application')
    def execute(
        self,
        *,
        user_id: uuid.UUID,
        message: str,
        conversation_id: Optional[uuid.UUID] = None,
        ui_context: Optional[dict] = None,
    ) -> Iterator[dict]:
        try:
            text = normalize_chat_message(self.policy, message)
        except ServerException as exc:
            yield _wire_event('assistant.error', {
                'code': getattr(exc.code, 'value', None) or str(exc.code),
                'detail': str(getattr(exc, 'detail', None) or exc),
            })
            return
        except ValidationAppException as exc:
            yield _wire_event('assistant.error', {
                'code': getattr(exc.code, 'value', None) or str(exc.code),
                'detail': str(getattr(exc, 'detail', None) or exc),
            })
            return

        self._turn.set_ui_context(ui_context)
        run_id = self._run_id or uuid7()
        self._turn.bind_cancel(run_id=run_id, cancel_event=self._cancel_event)

        try:
            conv_id, history, pending_title, pending_create = self._turn.prepare(
                user_id, text, conversation_id,
            )
        except Exception as exc:
            code = getattr(getattr(exc, 'code', None), 'value', None) or 'AI_005'
            detail = getattr(exc, 'detail', None) or str(exc)
            yield _wire_event('assistant.error', {'code': str(code), 'detail': str(detail)})
            return

        yield _wire_event('assistant.status', {
            'conversation_id': str(conv_id),
            'run_id': str(run_id),
            **status_payload(ASSISTANT_STATUS_INTERPRETING),
        })
        # Compat: clientes legacy que aún escuchan assistant.thinking.
        yield _wire_event('assistant.thinking', {
            'conversation_id': str(conv_id),
            'run_id': str(run_id),
        })

        model = self._turn._resolve_model()
        self._turn._start_run(
            run_id=run_id,
            user_id=user_id,
            conversation_id=None if pending_create else conv_id,
            model=model,
        )
        agent = self._turn.build_agent(model, run_id=run_id)
        reply = ''
        audits = []
        degraded = False
        streamed = False
        typing_sent = False
        cancelled = False

        try:
            for event in agent.iter_events(text, history=history):
                kind = event.get('kind')
                if kind == 'status':
                    yield _wire_event('assistant.status', {
                        'conversation_id': str(conv_id),
                        'run_id': str(run_id),
                        **status_payload(str(event.get('code') or ASSISTANT_STATUS_INTERPRETING)),
                    })
                elif kind == 'tool':
                    audit = event['audit']
                    yield _wire_event('assistant.tool', {
                        'tool_name': audit.tool_name,
                        'arguments': audit.arguments,
                        'success': audit.success,
                        'error_code': audit.error_code,
                    })
                elif kind == 'approval_required':
                    yield _wire_event('assistant.approval_required', {
                        'conversation_id': str(conv_id),
                        'run_id': str(event.get('run_id') or run_id),
                        'tool_name': event.get('tool_name') or '',
                        'arguments': event.get('arguments') or {},
                        'question': event.get('question') or '',
                        'action_summary': event.get('action_summary') or '',
                    })
                elif kind == 'typing':
                    typing_sent = True
                    yield _wire_event('assistant.status', {
                        'conversation_id': str(conv_id),
                        'run_id': str(run_id),
                        **status_payload(ASSISTANT_STATUS_COMPOSING),
                    })
                    yield _wire_event('assistant.typing', {
                        'conversation_id': str(conv_id),
                        'run_id': str(run_id),
                    })
                elif kind == 'token':
                    if not typing_sent:
                        typing_sent = True
                        yield _wire_event('assistant.status', {
                            'conversation_id': str(conv_id),
                            'run_id': str(run_id),
                            **status_payload(ASSISTANT_STATUS_COMPOSING),
                        })
                        yield _wire_event('assistant.typing', {
                            'conversation_id': str(conv_id),
                            'run_id': str(run_id),
                        })
                    streamed = True
                    yield _wire_event('assistant.token', {'text': event.get('text') or ''})
                elif kind == 'cancelled':
                    cancelled = True
                    reply = event.get('text') or 'The request was cancelled.'
                    audits = event.get('audits') or []
                    degraded = bool(event.get('degraded'))
                    yield _wire_event('assistant.cancelled', {
                        'conversation_id': str(conv_id),
                        'run_id': str(run_id),
                        'detail': reply,
                    })
                elif kind == 'final':
                    reply = event['text']
                    audits = event['audits']
                    degraded = event['degraded']
                    streamed = streamed or bool(event.get('streamed'))
        except Exception as exc:
            code = getattr(getattr(exc, 'code', None), 'value', None) or 'AI_005'
            detail = getattr(exc, 'detail', None) or str(exc)
            self._turn._finish_run(
                run_id,
                status='failed',
                conversation_id=None if pending_create else conv_id,
                error_code=str(code)[:40],
            )
            yield _wire_event('assistant.error', {'code': str(code), 'detail': str(detail)})
            return

        if cancelled:
            self._turn._finish_run(
                run_id,
                status='cancelled',
                conversation_id=None if pending_create else conv_id,
                degraded=degraded,
                step_count=len(audits),
                cancel_requested=True,
            )
            return

        if not streamed and reply:
            if not typing_sent:
                yield _wire_event('assistant.status', {
                    'conversation_id': str(conv_id),
                    'run_id': str(run_id),
                    **status_payload(ASSISTANT_STATUS_COMPOSING),
                })
                yield _wire_event('assistant.typing', {
                    'conversation_id': str(conv_id),
                    'run_id': str(run_id),
                })
            for chunk in chunk_text(reply):
                yield _wire_event('assistant.token', {'text': chunk})

        result = self._turn.persist(
            conv_id,
            user_id=user_id,
            user_text=text,
            reply=reply,
            audits=audits,
            degraded=degraded,
            pending_title=pending_title,
            pending_create=pending_create,
        )
        self._turn._finish_run(
            run_id,
            status='degraded' if degraded else 'completed',
            conversation_id=result.conversation_id,
            degraded=degraded,
            step_count=len(audits),
        )
        yield _wire_event('assistant.done', {
            'conversation_id': str(result.conversation_id),
            'run_id': str(run_id),
            'reply': result.reply,
            'degraded': result.degraded,
            'tools_used': [a.model_dump(mode='json') for a in result.tools_used],
            'streamed': streamed,
        })


class ListConversationsUseCase:
    def __init__(self, repository: IAssistantConversationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        *,
        user_id: uuid.UUID,
        limit: int = 20,
        q: Optional[str] = None,
    ) -> list[ConversationSummarySchema]:
        return self.repository.list_conversations(user_id, limit=limit, q=q)


class GetConversationMessagesUseCase:
    def __init__(self, repository: IAssistantConversationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ):
        if not self.repository.ensure_owned(conversation_id, user_id):
            raise NotFoundException(AppErrorCode.AI_CONVERSATION_NOT_FOUND)
        return self.repository.list_messages(conversation_id, limit=100)


class RenameConversationUseCase:
    def __init__(self, repository: IAssistantConversationRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        title: str,
    ) -> ConversationSummarySchema:
        cleaned = (title or '').strip()
        if not cleaned:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        if not self.repository.ensure_owned(conversation_id, user_id):
            raise NotFoundException(AppErrorCode.AI_CONVERSATION_NOT_FOUND)
        self.repository.touch_title(conversation_id, cleaned)
        summary = self.repository.get_summary(conversation_id)
        if summary is None:
            raise NotFoundException(AppErrorCode.AI_CONVERSATION_NOT_FOUND)
        return summary
