"""Consumidor WebSocket del assistant (chat con streaming nativo)."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import uuid

from django_tenants.utils import schema_context

from core.access.checker import AccessChecker
from core.errors import ERROR_REGISTRY
from core.errors.codes import AppErrorCode
from core.realtime.consumers import BaseRealtimeConsumer
from core.realtime.groups import RealtimeGroups

from client.features.communication.assistant.chat.domain.constants import ASSISTANT_CHAT_FEATURE
from client.features.communication.assistant.chat.presentation.bodies import ChatTurnBody

logger = logging.getLogger('app.ai')

_STREAM_QUEUE_MAX = 256
_CRITICAL_EVENT_TYPES = frozenset({
    'assistant.done',
    'assistant.error',
    'assistant.cancelled',
    'assistant.approval_required',
})


def assistant_busy_error_payload() -> dict:
    """Wire payload for AI_BUSY (registry detail — single source of truth)."""
    entry = ERROR_REGISTRY[AppErrorCode.AI_BUSY]
    return {
        'code': AppErrorCode.AI_BUSY.value,
        'detail': entry['detail'],
    }


def _is_critical_event(event) -> bool:
    return event is None or (
        isinstance(event, dict) and event.get('type') in _CRITICAL_EVENT_TYPES
    )


def _enqueue_stream_event(
    q: queue.Queue,
    event,
    *,
    cancel: threading.Event,
) -> bool:
    """
    Non-blocking enqueue with drop-oldest under backpressure.

    Never drops ``None`` (end sentinel) or critical done/error/cancelled events
    if we can reclaim space by discarding tokens/status first.
    After cancel, only critical events (and the end sentinel) are accepted.
    """
    if cancel.is_set() and not _is_critical_event(event):
        return False

    def _try_put(item) -> bool:
        try:
            q.put_nowait(item)
            return True
        except queue.Full:
            return False

    if _try_put(event):
        return True

    # Make room: drop oldest non-critical items.
    for _ in range(_STREAM_QUEUE_MAX):
        if cancel.is_set():
            return False
        try:
            oldest = q.get_nowait()
        except queue.Empty:
            break
        is_critical = _is_critical_event(oldest)
        if is_critical:
            # Put critical back; if still full, prefer keeping critical over new token.
            if not _try_put(oldest):
                return event is None or (
                    isinstance(event, dict) and event.get('type') in _CRITICAL_EVENT_TYPES
                )
            if _try_put(event):
                return True
            continue
        if _try_put(event):
            return True

    # Last attempt for sentinel / critical.
    if event is None or (
        isinstance(event, dict) and event.get('type') in _CRITICAL_EVENT_TYPES
    ):
        try:
            while True:
                q.get_nowait()
        except queue.Empty:
            pass
        return _try_put(event)
    return False


class AssistantChatConsumer(BaseRealtimeConsumer):
    """
    Request/response sobre la misma conexión.

    El turno corre en un hilo sync (``schema_context``) y publica eventos en
    una cola; el loop async los reenvía en cuanto llegan (tokens nativos del
    SLM mientras genera el JSON ``action=final``).
    """

    def get_groups(self) -> list[str]:
        return [RealtimeGroups.user(self.schema, self.user.id)]

    async def connect(self):
        if self.scope.get('audience') == 'admin':
            await self.close(code=4401)
            return
        self.user = self.scope.get('user')
        if not await asyncio.to_thread(self._has_chat_access):
            await self.close(code=4403)
            return
        self._busy = False
        self._stream_cancel: threading.Event | None = None
        self._active_run_id: uuid.UUID | None = None
        await super().connect()

    async def disconnect(self, code):
        cancel = getattr(self, '_stream_cancel', None)
        if cancel is not None:
            cancel.set()
        run_id = getattr(self, '_active_run_id', None)
        if run_id is not None:
            await asyncio.to_thread(self._mark_run_cancelled, run_id)
        self._busy = False
        await super().disconnect(code)

    def _run_control_stores(self):
        """Tenant+user scoped Redis control plane for cancel/HITL."""
        from core.ai.harness.approval import RunApprovalStore
        from core.ai.harness.cancel import RunCancelStore
        schema = getattr(self, 'schema', '') or ''
        user_id = getattr(getattr(self, 'user', None), 'id', None)
        return (
            RunCancelStore(schema=schema, user_id=user_id),
            RunApprovalStore(schema=schema, user_id=user_id),
        )

    def _mark_run_cancelled(self, run_id: uuid.UUID) -> None:
        cancel_store, approval_store = self._run_control_stores()
        cancel_store.request_cancel(run_id)
        # Unblock any HITL waiter so the agent thread can exit.
        approval_store.resolve(run_id, 'denied')

    def _resolve_approval(self, run_id: uuid.UUID, decision: str) -> None:
        if decision not in ('approved', 'denied'):
            return
        _, approval_store = self._run_control_stores()
        approval_store.resolve(run_id, decision)  # type: ignore[arg-type]

    def _bound_active_run_id(self, payload) -> uuid.UUID | None:
        """Only the connection's active run may be cancelled/approved."""
        active = getattr(self, '_active_run_id', None)
        if active is None:
            return None
        if not isinstance(payload, dict) or not payload.get('run_id'):
            return active
        try:
            claimed = uuid.UUID(str(payload['run_id']))
        except (ValueError, TypeError):
            return active
        if claimed != active:
            logger.warning(
                'assistant ignore foreign run_id claim=%s active=%s',
                claimed, active,
            )
            return None
        return active

    def _has_chat_access(self) -> bool:
        company = getattr(self.user, 'company', None)
        if company is None:
            return False
        result = AccessChecker.check_feature(
            company, ASSISTANT_CHAT_FEATURE, check_quota=False,
        )
        return result.is_allowed

    def _deny_chat_access(self, result) -> dict:
        code = getattr(getattr(result, 'error_code', None), 'value', None) or 'SUB_002'
        payload = {
            'code': str(code),
            'detail': result.detail or 'assistant chat is not allowed.',
        }
        context = getattr(result, 'context', None) or {}
        if context:
            payload['context'] = context
        return {
            'type': 'assistant.error',
            'payload': payload,
        }

    def _track_chat_usage(self) -> None:
        company = getattr(self.user, 'company', None)
        if company is None:
            return
        AccessChecker.track_usage(company, ASSISTANT_CHAT_FEATURE)

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            return
        msg_type = content.get('type')
        if msg_type == 'assistant.cancel':
            cancel = getattr(self, '_stream_cancel', None)
            if cancel is not None:
                cancel.set()
            payload = content.get('payload') or {}
            run_id = self._bound_active_run_id(payload)
            if run_id is not None:
                await asyncio.to_thread(self._mark_run_cancelled, run_id)
            return
        if msg_type in ('assistant.approve', 'assistant.deny'):
            payload = content.get('payload') or {}
            run_id = self._bound_active_run_id(payload)
            if run_id is not None:
                decision = 'approved' if msg_type == 'assistant.approve' else 'denied'
                await asyncio.to_thread(self._resolve_approval, run_id, decision)
            return
        if msg_type != 'assistant.chat':
            return

        raw_payload = content.get('payload') or {}
        if not isinstance(raw_payload, dict):
            raw_payload = {}
        body = ChatTurnBody(raw_payload)
        ok, errors = body.validate()
        if not ok:
            first = errors[0]
            await self.send_json({
                'type': 'assistant.error',
                'payload': {
                    'code': getattr(first.code, 'value', None) or str(first.code),
                    'detail': first.detail,
                    'field': first.field,
                },
            })
            return
        message = body.validated_data['message']
        conversation_id = body.validated_data.get('conversation_id')
        ui_context = body.validated_data.get('ui_context')
        if conversation_id is not None:
            conversation_id = uuid.UUID(str(conversation_id))

        access = await asyncio.to_thread(
            AccessChecker.check_feature,
            getattr(self.user, 'company', None),
            ASSISTANT_CHAT_FEATURE,
        ) if getattr(self.user, 'company', None) else None
        if access is None or not access.is_allowed:
            await self.send_json(self._deny_chat_access(access) if access else {
                'type': 'assistant.error',
                'payload': {
                    'code': 'SUB_002',
                    'detail': 'assistant chat is not allowed.',
                },
            })
            return
        if getattr(self, '_busy', False):
            await self.send_json({
                'type': 'assistant.error',
                'payload': assistant_busy_error_payload(),
            })
            return

        self._busy = True
        try:
            await self._stream_turn(
                message=message,
                conversation_id=conversation_id,
                ui_context=ui_context,
            )
        except Exception as exc:
            logger.exception('assistant ws turn failed: %s', exc)
            await self.send_json({
                'type': 'assistant.error',
                'payload': {
                    'code': 'AI_005',
                    'detail': str(getattr(exc, 'detail', None) or exc),
                },
            })
        finally:
            self._busy = False

    async def _stream_turn(self, *, message: str, conversation_id, ui_context=None):
        q: queue.Queue = queue.Queue(maxsize=_STREAM_QUEUE_MAX)
        cancel = threading.Event()
        self._stream_cancel = cancel
        schema = self.schema
        user_id = self.user.id

        from core.ids import uuid7

        run_id = uuid7()
        self._active_run_id = run_id

        def producer():
            try:
                from client.features.communication.assistant.chat.application.use_cases import ChatTurnStreamUseCase
                from client.features.communication.assistant.chat.infrastructure.repositories import (
                    DjangoAssistantConversationRepository,
                )
                from client.features.communication.assistant.chat.infrastructure.run_repository import (
                    DjangoAssistantAgentRunRepository,
                )
                from client.features.communication.assistant.chat.presentation.runtime import load_chat_runtime

                with schema_context(schema):
                    from client.features.communication.assistant.credentials.infrastructure.repositories import (
                        DjangoAssistantCredentialRepository,
                    )
                    policy, registry = load_chat_runtime()
                    for event in ChatTurnStreamUseCase(
                        DjangoAssistantConversationRepository(),
                        registry,
                        policy=policy,
                        run_repository=DjangoAssistantAgentRunRepository(),
                        credential_repository=DjangoAssistantCredentialRepository(),
                        cancel_event=cancel,
                        run_id=run_id,
                        tenant_schema=schema,
                        actor_user_id=user_id,
                    ).execute(
                        user_id=user_id,
                        message=message,
                        conversation_id=conversation_id,
                        ui_context=ui_context,
                    ):
                        if not _enqueue_stream_event(q, event, cancel=cancel):
                            if _is_critical_event(event):
                                continue
                            break
            except Exception as exc:
                logger.exception('assistant producer failed: %s', exc)
                _enqueue_stream_event(
                    q,
                    {
                        'type': 'assistant.error',
                        'payload': {
                            'code': str(
                                getattr(getattr(exc, 'code', None), 'value', None) or 'AI_005'
                            ),
                            'detail': str(getattr(exc, 'detail', None) or exc),
                        },
                    },
                    cancel=cancel,
                )
            finally:
                _enqueue_stream_event(q, None, cancel=cancel)

        thread = threading.Thread(target=producer, name='assistant-stream', daemon=True)
        thread.start()

        try:
            while True:
                try:
                    event = await asyncio.to_thread(q.get, True, 1.0)
                except queue.Empty:
                    if not thread.is_alive():
                        try:
                            event = q.get_nowait()
                        except queue.Empty:
                            break
                    else:
                        continue
                if event is None:
                    break
                if isinstance(event, dict):
                    await self.send_json(event)
                    if event.get('type') == 'assistant.done':
                        await asyncio.to_thread(self._track_chat_usage)
                    if event.get('type') == 'assistant.token':
                        await asyncio.sleep(0)
        except asyncio.CancelledError:
            cancel.set()
            await asyncio.to_thread(self._mark_run_cancelled, run_id)
            raise
        finally:
            cancel.set()
            self._stream_cancel = None
            self._active_run_id = None
            await asyncio.to_thread(thread.join, 5)
