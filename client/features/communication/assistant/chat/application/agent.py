"""Bucle de agente estrecho para SLM (JSON tool / final) + stream nativo.

Delega parseo, gate de hechos, cancelación y hooks al harness ``core/ai/harness``.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from typing import Iterator, Optional

from core.ai.assistant_catalog import ASSISTANT_DEFAULT_OUT_OF_SCOPE
from core.ai.domain.interfaces import IChatModel
from core.ai.domain.schemas import ChatOptions, Message, Prompt
from core.ai.harness.approval import RunApprovalStore
from core.ai.harness.cancel import RunCancelStore, is_cancelled
from core.ai.harness.environment import CapabilityBoundary
from core.ai.harness.extensions import HookBus, HookPoint
from core.ai.harness.facts_gate import enforce_tool_before_facts
from core.ai.harness.parse import chunk_text as harness_chunk_text
from core.ai.harness.parse import parse_agent_action as harness_parse_agent_action
from core.ai.resilience import stream_accumulate_or

from client.features.communication.assistant.chat.application.json_text_stream import FinalTextStreamExtractor
from client.features.communication.assistant.chat.application.orientation import is_orientation_question
from client.features.communication.assistant.chat.application.ui_context import format_ui_context_for_prompt
from client.features.communication.assistant.chat.domain.schemas import AgentAction, ToolCallAuditSchema
from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry
from core.ai.assistant_status import (
    ASSISTANT_STATUS_COMPOSING,
    ASSISTANT_STATUS_INTERPRETING,
    ASSISTANT_STATUS_REVIEWING_RESULTS,
    status_for_tool,
)
from core.trace import trace_layer

logger = logging.getLogger('app.ai')

_MAX_STEPS = 4
_HISTORY_TURNS = 8
_FALLBACK_JSON = (
    '{"action":"final","text":'
    '"I could not reach the assistant right now. Please try again."}'
)
_NO_TOOLS_CATALOG = (
    '(none — orientation question; answer with action=final from screen context only)'
)

_SYSTEM_TEMPLATE = """You are the assistant for this product.
Reply in the same language as the user (Spanish if they write Spanish). Keep answers short and clear.
You NEVER invent data that a tool did not return.
You MUST reply with ONE JSON object only (no markdown, no extra text):
{{"action":"tool","name":"<tool_name>","arguments":{{...}}}}
or
{{"action":"final","text":"<short answer>"}}

Available tools (whitelist only):
{catalog}

{ui_context}

Rules:
- Only call tools from the list. If the list is empty, you MUST use action=final.
- Never write/update/delete data.
- If data is missing after tools, say so honestly.
- Out-of-scope (no matching tool / cannot answer warehouse data): reply with exactly: {out_of_scope}
- Warehouse facts (stock, orders, catalog): only after a successful tool result in this turn.
- Orientation (where am I / which module or tab / what is this screen for): answer ONLY from
  Visible screen-context fields with action=final. Do NOT call warehouse tools.
- Prefer Module, Tab, and Purpose in answers. NEVER quote Route, Module code, Module id,
  Feature, Page section key, Entity type, or Entity id to the user.
- When tools are available for non-orientation questions, use screen context only as a hint
  for which tools or filters to try.
{facts_rule}

Examples (orientation — action=final, no tools):
User: "En que pantalla estoy?"
Assistant: {{"action":"final","text":"Estás en el módulo Inventarios, pestaña Referencias."}}
User: "En que pestaña estoy y para que sirve este modulo?"
Assistant: {{"action":"final","text":"Pestaña Referencias. Este módulo administra el maestro de productos, tipos y unidades del inventario."}}

Examples (warehouse facts — tool then final):
User: "Cuantas bodegas tenemos operando?"
Assistant: {{"action":"tool","name":"list_warehouses","arguments":{{"status":"ACTIVE"}}}}
"""


def parse_agent_action(raw: str) -> Optional[AgentAction]:
    """Compat: convierte el contrato harness a ``AgentAction`` de producto."""
    parsed = harness_parse_agent_action(raw)
    if parsed is None:
        return None
    return AgentAction(
        action=parsed.action,
        name=parsed.name,
        arguments=parsed.arguments,
        text=parsed.text,
    )


def chunk_text(text: str, size: int = 10) -> Iterator[str]:
    yield from harness_chunk_text(text, size=size)


class AssistantAgent:
    """Orquesta SLM ↔ tools. El modelo nunca toca la BD."""

    def __init__(
        self,
        model: IChatModel,
        registry: ToolRegistry,
        *,
        max_steps: int = _MAX_STEPS,
        history_turns: int = _HISTORY_TURNS,
        out_of_scope_message: str = '',
        require_tool_before_facts: bool = True,
        ui_context: dict | None = None,
        run_id: uuid.UUID | None = None,
        cancel_event: threading.Event | None = None,
        cancel_store: RunCancelStore | None = None,
        approval_store: RunApprovalStore | None = None,
        hooks: HookBus | None = None,
        capability: CapabilityBoundary | None = None,
        approval_timeout_s: float = 120.0,
    ):
        self.model = model
        self.registry = registry
        self.max_steps = max_steps
        self.history_turns = history_turns
        self.out_of_scope_message = (
            (out_of_scope_message or '').strip()
            or ASSISTANT_DEFAULT_OUT_OF_SCOPE
        )
        self.require_tool_before_facts = require_tool_before_facts
        self.ui_context = ui_context or {}
        self.run_id = run_id
        self.cancel_event = cancel_event
        self.cancel_store = cancel_store or RunCancelStore()
        self.approval_store = approval_store or RunApprovalStore()
        self.approval_timeout_s = approval_timeout_s
        self.hooks = hooks or HookBus()
        self.capability = capability or CapabilityBoundary(registry.names())

    def _cancelled(self) -> bool:
        return is_cancelled(
            run_id=self.run_id,
            local=self.cancel_event,
            store=self.cancel_store,
        )

    @trace_layer('application')
    def run(
        self,
        user_message: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[ToolCallAuditSchema], bool, bool]:
        """Returns (final_text, tool_audits, degraded, cancelled)."""
        reply = ''
        audits: list[ToolCallAuditSchema] = []
        degraded = False
        cancelled = False
        for event in self.iter_events(user_message, history=history):
            kind = event.get('kind')
            if kind == 'tool':
                audits.append(event['audit'])
            elif kind == 'final':
                reply = event['text']
                audits = event['audits']
                degraded = event['degraded']
            elif kind == 'cancelled':
                cancelled = True
                reply = event.get('text') or 'The request was cancelled.'
                audits = event.get('audits') or audits
                degraded = bool(event.get('degraded'))
        return reply, audits, degraded, cancelled

    def iter_events(
        self,
        user_message: str,
        *,
        history: list[dict[str, str]] | None = None,
    ) -> Iterator[dict]:
        """
        Eventos internos:

        - ``status`` — fase operativa (interpreting / tool process / composing)
        - ``typing`` / ``token`` — stream nativo del campo text (action=final)
        - ``tool`` — auditoría de tool
        - ``cancelled`` — aborto solicitado
        - ``final`` — texto completo + audits + degraded + streamed (bool)
        """
        self.hooks.emit(HookPoint.BEFORE_RUN, user_message=user_message, run_id=self.run_id)
        orientation = is_orientation_question(user_message)
        tools_disabled = orientation
        if tools_disabled:
            catalog = _NO_TOOLS_CATALOG
            facts_rule = (
                'This turn is orientation-only. Reply with action=final using Visible '
                'screen-context fields (Module / Tab / Purpose). Do not call tools. '
                'If screen context is missing, say briefly that you do not know the '
                'current screen — never invent it and never use warehouse tools.'
            )
        elif self.require_tool_before_facts:
            catalog = self.registry.catalog_for_prompt() or '(none)'
            facts_rule = (
                'If no tool succeeded in this turn, do not assert warehouse data; '
                'use the out-of-scope reply. Orientation answers from screen context '
                'do not require a tool.'
            )
        else:
            catalog = self.registry.catalog_for_prompt() or '(none)'
            facts_rule = (
                'You may answer generally without a tool, but never invent tenant data.'
            )

        ui_block = format_ui_context_for_prompt(self.ui_context)
        system = _SYSTEM_TEMPLATE.format(
            catalog=catalog,
            out_of_scope=self.out_of_scope_message,
            facts_rule=facts_rule,
            ui_context=ui_block or 'Operator screen context: (not provided).',
        )
        messages: list[Message] = []
        history_limit = max(1, self.history_turns)
        for turn in (history or [])[-history_limit:]:
            role = turn.get('role')
            content = turn.get('content') or ''
            if role == 'user':
                messages.append(Message.user(content))
            elif role == 'assistant':
                messages.append(Message.assistant(content))

        messages.append(Message.user(user_message))
        audits: list[ToolCallAuditSchema] = []
        degraded = False
        opts = ChatOptions(metadata={'feature': 'assistant.chat'})

        for step_index in range(self.max_steps):
            if self._cancelled():
                self.hooks.emit(HookPoint.ON_CANCEL, run_id=self.run_id, step=step_index)
                yield {
                    'kind': 'cancelled',
                    'text': 'The request was cancelled.',
                    'audits': audits,
                    'degraded': degraded,
                }
                return

            yield {'kind': 'status', 'code': ASSISTANT_STATUS_INTERPRETING}
            prompt = Prompt(system=system, messages=list(messages), options=opts)
            self.hooks.emit(HookPoint.BEFORE_MODEL, prompt=prompt, step=step_index)
            raw_parts: list[str] = []
            step_degraded = False
            extractor = FinalTextStreamExtractor()
            typing_sent = False
            streamed_any = False

            for piece in stream_accumulate_or(
                self.model,
                prompt,
                fallback=_FALLBACK_JSON,
                feature='assistant.chat',
            ):
                if self._cancelled():
                    self.hooks.emit(HookPoint.ON_CANCEL, run_id=self.run_id, step=step_index)
                    yield {
                        'kind': 'cancelled',
                        'text': 'The request was cancelled.',
                        'audits': audits,
                        'degraded': degraded or step_degraded,
                    }
                    return
                delta = piece.get('delta') or ''
                if piece.get('degraded'):
                    step_degraded = True
                raw_parts.append(delta)
                for text_bit in extractor.feed(delta):
                    if not typing_sent:
                        yield {'kind': 'status', 'code': ASSISTANT_STATUS_COMPOSING}
                        yield {'kind': 'typing'}
                        typing_sent = True
                    streamed_any = True
                    yield {'kind': 'token', 'text': text_bit}

            if step_degraded:
                degraded = True

            completion_text = ''.join(raw_parts)
            self.hooks.emit(
                HookPoint.AFTER_MODEL,
                completion=completion_text,
                degraded=step_degraded,
                step=step_index,
            )
            action = parse_agent_action(completion_text)
            if action is None:
                text = 'I did not understand the model response. Please rephrase the question.'
                yield from self._flush_final_tokens(
                    text, extractor, typing_sent=typing_sent, streamed_any=streamed_any,
                )
                yield from self._emit_final(
                    text, audits, degraded, streamed_any or bool(extractor.emitted_text),
                )
                return

            if action.action == 'final':
                text = (action.text or '').strip() or 'Done.'
                had_success = any(a.success for a in audits)
                text = enforce_tool_before_facts(
                    text,
                    require_tool_before_facts=self.require_tool_before_facts,
                    orientation=orientation,
                    had_successful_tool=had_success,
                    out_of_scope_message=self.out_of_scope_message,
                )
                yield from self._flush_final_tokens(
                    text, extractor, typing_sent=typing_sent, streamed_any=streamed_any,
                )
                yield from self._emit_final(
                    text, audits, degraded, streamed_any or bool(extractor.emitted_text),
                )
                return

            name = action.name or ''
            arguments = action.arguments or {}
            yield {'kind': 'status', 'code': status_for_tool(name)}

            if tools_disabled:
                audit = ToolCallAuditSchema(
                    tool_name=name,
                    arguments=arguments,
                    success=False,
                    error_code='ORIENTATION_NO_TOOLS',
                    result_preview='Orientation questions cannot use warehouse tools',
                )
                audits.append(audit)
                yield {'kind': 'tool', 'audit': audit}
                messages.append(Message.assistant(completion_text))
                messages.append(Message.user(
                    'Tool result: ERROR orientation questions cannot call warehouse tools. '
                    'Respond with action=final using Visible screen-context fields only.',
                ))
                yield {'kind': 'status', 'code': ASSISTANT_STATUS_REVIEWING_RESULTS}
                continue

            if self.registry.get(name) is None or not self.capability.allows(name):
                audit = ToolCallAuditSchema(
                    tool_name=name,
                    arguments=arguments,
                    success=False,
                    error_code='TOOL_NOT_ALLOWED',
                    result_preview='Tool not in whitelist',
                )
                audits.append(audit)
                yield {'kind': 'tool', 'audit': audit}
                messages.append(Message.assistant(completion_text))
                messages.append(Message.user(
                    f'Tool result: ERROR tool "{name}" is not allowed. '
                    f'Use only: {", ".join(self.registry.names())}. '
                    'Respond with final JSON.',
                ))
                yield {'kind': 'status', 'code': ASSISTANT_STATUS_REVIEWING_RESULTS}
                continue

            self.hooks.emit(
                HookPoint.BEFORE_TOOL,
                tool_name=name,
                arguments=arguments,
                step=step_index,
            )
            try:
                # Never pass model-invented confirmed — server flag only.
                result = self.registry.execute(name, arguments, confirmed=False)
                preview = result if isinstance(result, str) else json.dumps(result, default=str)
                audit = ToolCallAuditSchema(
                    tool_name=name,
                    arguments=arguments,
                    success=True,
                    result_preview=preview[:2000],
                )
                audits.append(audit)
                self.hooks.emit(HookPoint.AFTER_TOOL, audit=audit, step=step_index)
                yield {'kind': 'tool', 'audit': audit}
                messages.append(Message.assistant(completion_text))
                messages.append(Message.user(
                    f'Tool result for {name}: {preview}\n'
                    'Continue. Prefer action=final when you can answer.',
                ))
            except PermissionError as exc:
                # HITL: wait for operator approve/deny before retrying with confirmed=True.
                for event in self._await_tool_approval(
                    name=name,
                    arguments=arguments,
                    completion_text=completion_text,
                    messages=messages,
                    audits=audits,
                    degraded=degraded,
                    step_index=step_index,
                    reason=str(exc),
                ):
                    if event.get('kind') in ('cancelled', 'final'):
                        yield event
                        return
                    yield event
                continue
            except Exception as exc:
                logger.warning('assistant tool %s failed: %s', name, exc)
                code = getattr(getattr(exc, 'code', None), 'value', None) or type(exc).__name__
                audit = ToolCallAuditSchema(
                    tool_name=name,
                    arguments=arguments,
                    success=False,
                    error_code=str(code)[:40],
                    result_preview=str(exc)[:500],
                )
                audits.append(audit)
                self.hooks.emit(HookPoint.AFTER_TOOL, audit=audit, step=step_index)
                yield {'kind': 'tool', 'audit': audit}
                messages.append(Message.assistant(completion_text))
                messages.append(Message.user(
                    f'Tool result for {name}: ERROR {exc}. '
                    'Explain briefly with action=final.',
                ))

            yield {'kind': 'status', 'code': ASSISTANT_STATUS_REVIEWING_RESULTS}

        text = 'I reached the step limit. Please rephrase with more detail.'
        yield from self._emit_final(text, audits, degraded, False)

    def _await_tool_approval(
        self,
        *,
        name: str,
        arguments: dict,
        completion_text: str,
        messages: list[Message],
        audits: list[ToolCallAuditSchema],
        degraded: bool,
        step_index: int,
        reason: str,
    ) -> Iterator[dict]:
        """Publica ``approval_required``, espera HITL y reintenta o deniega."""
        if self.run_id is None:
            audit = ToolCallAuditSchema(
                tool_name=name,
                arguments=arguments,
                success=False,
                error_code='CONFIRMATION_REQUIRED',
                result_preview=reason,
            )
            audits.append(audit)
            yield {'kind': 'tool', 'audit': audit}
            messages.append(Message.assistant(completion_text))
            messages.append(Message.user(
                f'Tool result: ERROR {reason}. Ask the user to confirm, then final.',
            ))
            return

        self.approval_store.begin_wait(self.run_id)
        on_awaiting = getattr(self, 'on_awaiting_approval', None)
        if callable(on_awaiting):
            try:
                on_awaiting(self.run_id)
            except Exception as exc:
                logger.debug('awaiting_approval persist skipped: %s', exc)
        yield {
            'kind': 'approval_required',
            'run_id': str(self.run_id),
            'tool_name': name,
            'arguments': arguments,
            'question': (
                f'¿Confirmas ejecutar «{name}»? '
                'La acción quedará en pausa hasta que apruebes o rechaces.'
            ),
            'action_summary': name,
        }
        decision = self.approval_store.wait(
            self.run_id,
            timeout_s=self.approval_timeout_s,
            cancel_check=self._cancelled,
        )
        self.approval_store.clear(self.run_id)

        if decision is None or self._cancelled():
            self.hooks.emit(HookPoint.ON_CANCEL, run_id=self.run_id, step=step_index)
            yield {
                'kind': 'cancelled',
                'text': 'The request was cancelled.',
                'audits': audits,
                'degraded': degraded,
            }
            return

        if decision == 'denied':
            audit = ToolCallAuditSchema(
                tool_name=name,
                arguments=arguments,
                success=False,
                error_code='APPROVAL_DENIED',
                result_preview='Operator denied the tool call',
            )
            audits.append(audit)
            self.hooks.emit(HookPoint.AFTER_TOOL, audit=audit, step=step_index)
            yield {'kind': 'tool', 'audit': audit}
            messages.append(Message.assistant(completion_text))
            messages.append(Message.user(
                f'Tool result for {name}: ERROR operator denied the action. '
                'Explain briefly with action=final.',
            ))
            yield {'kind': 'status', 'code': ASSISTANT_STATUS_REVIEWING_RESULTS}
            return

        # Server-side confirmation only — never trust model args.
        retry_args = self.registry._sanitize_arguments(arguments)
        try:
            result = self.registry.execute(name, retry_args, confirmed=True)
            preview = result if isinstance(result, str) else json.dumps(result, default=str)
            audit = ToolCallAuditSchema(
                tool_name=name,
                arguments=retry_args,
                success=True,
                result_preview=preview[:2000],
            )
            audits.append(audit)
            self.hooks.emit(HookPoint.AFTER_TOOL, audit=audit, step=step_index)
            yield {'kind': 'tool', 'audit': audit}
            messages.append(Message.assistant(completion_text))
            messages.append(Message.user(
                f'Tool result for {name}: {preview}\n'
                'Continue. Prefer action=final when you can answer.',
            ))
            yield {'kind': 'status', 'code': ASSISTANT_STATUS_REVIEWING_RESULTS}
        except Exception as exc:
            logger.warning('assistant tool %s after approval failed: %s', name, exc)
            code = getattr(getattr(exc, 'code', None), 'value', None) or type(exc).__name__
            audit = ToolCallAuditSchema(
                tool_name=name,
                arguments=retry_args,
                success=False,
                error_code=str(code)[:40],
                result_preview=str(exc)[:500],
            )
            audits.append(audit)
            self.hooks.emit(HookPoint.AFTER_TOOL, audit=audit, step=step_index)
            yield {'kind': 'tool', 'audit': audit}
            messages.append(Message.assistant(completion_text))
            messages.append(Message.user(
                f'Tool result for {name}: ERROR {exc}. '
                'Explain briefly with action=final.',
            ))
            yield {'kind': 'status', 'code': ASSISTANT_STATUS_REVIEWING_RESULTS}

    def _emit_final(
        self,
        text: str,
        audits: list[ToolCallAuditSchema],
        degraded: bool,
        streamed: bool,
    ) -> Iterator[dict]:
        self.hooks.emit(
            HookPoint.ON_FINAL,
            text=text,
            audits=audits,
            degraded=degraded,
            run_id=self.run_id,
        )
        yield {
            'kind': 'final',
            'text': text,
            'audits': audits,
            'degraded': degraded,
            'streamed': streamed,
        }

    def _flush_final_tokens(
        self,
        final_text: str,
        extractor: FinalTextStreamExtractor,
        *,
        typing_sent: bool,
        streamed_any: bool,
    ) -> Iterator[dict]:
        """Completa tokens que el extractor no alcanzó a emitir (o fallback paced)."""
        rest = extractor.remaining_from(final_text)
        if not rest:
            return
        if not typing_sent and not streamed_any:
            yield {'kind': 'status', 'code': ASSISTANT_STATUS_COMPOSING}
            yield {'kind': 'typing'}
        if streamed_any or extractor.emitted_text:
            yield {'kind': 'token', 'text': rest}
        else:
            for bit in chunk_text(rest):
                yield {'kind': 'token', 'text': bit}
