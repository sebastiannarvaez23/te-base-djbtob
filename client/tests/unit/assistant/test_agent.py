"""Unit tests — agente assistant (Fase 3 MVP)."""

from __future__ import annotations

import json
import uuid
from typing import List, Tuple

import pytest
from django.test import override_settings

from core.ai.domain.schemas import FinishReason, Prompt, TokenUsage
from core.ai.infrastructure.base import BaseChatModel
from core.errors import AppErrorCode, ServerException

from client.features.communication.assistant.chat.application.agent import AssistantAgent, parse_agent_action
from client.features.communication.assistant.chat.application.use_cases import ChatTurnUseCase, GetAssistantStatusUseCase
from client.features.communication.assistant.chat.domain.schemas import AgentAction
from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry, ToolSpec


class ScriptedChatModel(BaseChatModel):
    """Devuelve respuestas JSON predefinidas en orden (sin red)."""

    provider_name = 'scripted'

    def __init__(self, responses: List[str], *, stream_chars: bool = True):
        self.model_name = 'scripted-1'
        self._responses = list(responses)
        self._stream_chars = stream_chars
        self.calls = 0

    def _generate(self, prompt: Prompt) -> Tuple[str, TokenUsage, FinishReason]:
        self.calls += 1
        if not self._responses:
            text = '{"action":"final","text":"fin"}'
        else:
            text = self._responses.pop(0)
        return text, TokenUsage(input_tokens=1, output_tokens=1), FinishReason.STOP

    def stream(self, prompt: Prompt):
        """Stream carácter a carácter para ejercitar el extractor nativo."""
        text, _, _ = self._generate(prompt)
        if not self._stream_chars:
            yield text
            return
        for ch in text:
            yield ch


from core.ids import uuid7


class MemoryAssistantRepo:
    def __init__(self):
        self.conversations = {}
        self.messages = {}
        self.tools = []

    def get_or_create(self, *, user_id, conversation_id=None):
        if conversation_id:
            assert conversation_id in self.conversations
            return conversation_id
        return self.create(user_id=user_id)

    def create(self, *, user_id, conversation_id=None):
        cid = conversation_id or uuid7()
        self.conversations[cid] = user_id
        self.messages.setdefault(cid, [])
        return cid

    def ensure_owned(self, conversation_id, user_id):
        return self.conversations.get(conversation_id) == user_id

    def add_message(self, conversation_id, *, role, content):
        from client.features.communication.assistant.chat.domain.schemas import ChatMessageSchema
        from datetime import datetime
        msg = ChatMessageSchema(
            id=uuid7(),
            role=role,
            content=content,
            created_at=datetime.utcnow(),
        )
        self.messages.setdefault(conversation_id, []).append(msg)
        return msg

    def list_messages(self, conversation_id, *, limit=40):
        return list(self.messages.get(conversation_id, []))[-limit:]

    def list_conversations(self, user_id, *, limit=20, q=None):
        return []

    def touch_title(self, conversation_id, title):
        pass

    def get_summary(self, conversation_id):
        return None

    def record_tool_call(self, conversation_id, **kwargs):
        self.tools.append({'conversation_id': conversation_id, **kwargs})

    def save_turn(self, conversation_id, *, user_text, reply, tool_audits, pending_title=None):
        self.add_message(conversation_id, role='user', content=user_text)
        if pending_title:
            self.touch_title(conversation_id, pending_title)
        assistant_msg = self.add_message(conversation_id, role='assistant', content=reply)
        for audit in tool_audits:
            self.record_tool_call(
                conversation_id,
                tool_name=audit['tool_name'],
                arguments=audit.get('arguments') or {},
                result_preview=audit.get('result_preview') or '',
                success=bool(audit.get('success', True)),
                error_code=audit.get('error_code') or '',
                message_id=assistant_msg.id,
            )
        return assistant_msg


@pytest.mark.unit
class TestParseAgentAction:

    def test_parses_tool_json(self):
        action = parse_agent_action(
            '{"action":"tool","name":"list_orders","arguments":{"limit":3}}',
        )
        assert action is not None
        assert action.action == 'tool'
        assert action.name == 'list_orders'
        assert action.arguments['limit'] == 3

    def test_parses_final_json(self):
        action = parse_agent_action('{"action":"final","text":"Hola"}')
        assert action == AgentAction(action='final', text='Hola')

    def test_prose_becomes_final(self):
        action = parse_agent_action('Todo bien por ahora')
        assert action.action == 'final'
        assert 'Todo bien' in action.text

    def test_extracts_first_json_when_trailing_junk(self):
        action = parse_agent_action(
            'Sure. {"action":"final","text":"Solo el primero"} {"action":"tool","name":"x"}',
        )
        assert action.action == 'final'
        assert action.text == 'Solo el primero'

    def test_extracts_tool_with_braces_in_string(self):
        action = parse_agent_action(
            'noise {"action":"tool","name":"list_orders","arguments":{"q":"a{b}"}} trailing',
        )
        assert action.action == 'tool'
        assert action.name == 'list_orders'
        assert action.arguments['q'] == 'a{b}'


@pytest.mark.unit
class TestToolRegistryGuardrails:

    def test_rejects_unknown_tool(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='list_orders',
            description='x',
            parameters_schema={},
            handler=lambda args: 'ok',
        ))
        agent = AssistantAgent(
            ScriptedChatModel([
                '{"action":"tool","name":"drop_database","arguments":{}}',
                '{"action":"final","text":"No puedo hacer eso"}',
            ]),
            registry,
        )
        reply, audits, _, _cancelled = agent.run('borra todo')
        assert any(a.error_code == 'TOOL_NOT_ALLOWED' for a in audits)
        assert 'drop_database' not in [a.tool_name for a in audits if a.success]
        assert reply

    def test_writable_requires_confirmation_flag(self):
        registry = ToolRegistry()
        with pytest.raises(ValueError):
            registry.register(ToolSpec(
                name='delete_order',
                description='bad',
                parameters_schema={},
                handler=lambda args: None,
                read_only=False,
                requires_confirmation=False,
            ))

    def test_writable_blocked_without_confirmed(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='cancel_order',
            description='cancel',
            parameters_schema={},
            handler=lambda args: 'done',
            read_only=False,
            requires_confirmation=True,
        ))
        with pytest.raises(PermissionError):
            registry.execute('cancel_order', {'number': 'X'})
        # Model-invented confirmed in args must NOT authorize.
        with pytest.raises(PermissionError):
            registry.execute('cancel_order', {'number': 'X', 'confirmed': True})
        assert registry.execute('cancel_order', {'number': 'X'}, confirmed=True) == 'done'

    def test_happy_path_tool_then_final(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='list_orders',
            description='list',
            parameters_schema={},
            handler=lambda args: json.dumps({'total': 0, 'items': []}),
        ))
        agent = AssistantAgent(
            ScriptedChatModel([
                '{"action":"tool","name":"list_orders","arguments":{"limit":5}}',
                '{"action":"final","text":"No hay pedidos"}',
            ]),
            registry,
        )
        reply, audits, degraded, _cancelled = agent.run('¿hay pedidos?')
        assert reply == 'No hay pedidos'
        assert len(audits) == 1
        assert audits[0].success
        assert not degraded

    def test_hard_gate_blocks_warehouse_facts_without_tool(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='list_orders',
            description='list',
            parameters_schema={},
            handler=lambda args: '{}',
        ))
        agent = AssistantAgent(
            ScriptedChatModel([
                '{"action":"final","text":"Tienes 12 pedidos en stock pendientes"}',
            ]),
            registry,
            require_tool_before_facts=True,
            out_of_scope_message='OUT_OF_SCOPE',
        )
        reply, audits, _, _cancelled = agent.run('cuantos pedidos hay')
        assert reply == 'OUT_OF_SCOPE'
        assert audits == []

    def test_cancel_aborts_before_model(self):
        import threading
        registry = ToolRegistry()
        model = ScriptedChatModel(['{"action":"final","text":"no"}'])
        cancel = threading.Event()
        cancel.set()
        agent = AssistantAgent(model, registry, cancel_event=cancel)
        events = list(agent.iter_events('hola'))
        assert events[-1]['kind'] == 'cancelled'
        assert model.calls == 0

    def test_iter_events_emits_tool_then_final(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='list_orders',
            description='list',
            parameters_schema={},
            handler=lambda args: '{}',
        ))
        agent = AssistantAgent(
            ScriptedChatModel([
                '{"action":"tool","name":"list_orders","arguments":{}}',
                '{"action":"final","text":"Ok"}',
            ]),
            registry,
        )
        events = list(agent.iter_events('x'))
        kinds = [e['kind'] for e in events]
        assert 'status' in kinds
        assert kinds.count('status') >= 2  # interpreting + tool process (+ composing)
        assert any(
            e.get('kind') == 'status' and e.get('code') == 'searching_orders'
            for e in events
        )
        assert 'tool' in kinds
        assert kinds[-1] == 'final'
        assert 'typing' in kinds
        assert 'token' in kinds
        assert ''.join(e['text'] for e in events if e.get('kind') == 'token') == 'Ok'


@pytest.mark.unit
class TestChunkText:

    def test_chunks_cover_full_text(self):
        from client.features.communication.assistant.chat.application.agent import chunk_text
        text = 'abcdefghij'
        assert ''.join(chunk_text(text, size=3)) == text


@pytest.mark.unit
class TestChatTurnStreamUseCase:

    @override_settings(AI_ENABLED=True, AI_PROVIDER='fake')
    def test_stream_emits_wire_protocol(self):
        from client.features.communication.assistant.chat.application.use_cases import ChatTurnStreamUseCase

        repo = MemoryAssistantRepo()
        registry = ToolRegistry()
        model = ScriptedChatModel(['{"action":"final","text":"Hola stream"}'])
        events = list(
            ChatTurnStreamUseCase(repo, registry, model=model).execute(
                user_id=uuid.uuid4(),
                message='hola',
            ),
        )
        types = [e['type'] for e in events]
        assert types[0] == 'assistant.status'
        assert events[0]['payload']['code'] == 'interpreting'
        assert 'assistant.thinking' in types  # legacy compat
        assert 'assistant.typing' in types
        assert 'assistant.token' in types
        assert types[-1] == 'assistant.done'
        assert any(
            e['type'] == 'assistant.status' and e['payload'].get('code') == 'composing'
            for e in events
        )
        assert ''.join(
            e['payload']['text'] for e in events if e['type'] == 'assistant.token'
        ) == 'Hola stream'
        assert events[-1]['payload'].get('streamed') is True

    @override_settings(AI_ENABLED=False, AI_PROVIDER='local')
    def test_stream_errors_when_disabled(self):
        from client.features.communication.assistant.chat.application.use_cases import ChatTurnStreamUseCase

        repo = MemoryAssistantRepo()
        model = ScriptedChatModel(['{"action":"final","text":"x"}'])
        events = list(
            ChatTurnStreamUseCase(repo, ToolRegistry(), model=model).execute(
                user_id=uuid.uuid4(),
                message='hola',
            ),
        )
        assert len(events) == 1
        assert events[0]['type'] == 'assistant.error'
        assert events[0]['payload']['code'] == 'AI_006'
        assert model.calls == 0


@pytest.mark.unit
class TestFinalTextStreamExtractor:

    def test_extracts_text_incrementally(self):
        from client.features.communication.assistant.chat.application.json_text_stream import (
            FinalTextStreamExtractor,
        )

        ext = FinalTextStreamExtractor()
        raw = '{"action":"final","text":"Hola mundo"}'
        out = []
        for ch in raw:
            out.extend(ext.feed(ch))
        assert ''.join(out) == 'Hola mundo'
        assert ext.emitted_text == 'Hola mundo'
        assert ext.is_done

    def test_ignores_tool_action(self):
        from client.features.communication.assistant.chat.application.json_text_stream import (
            FinalTextStreamExtractor,
        )

        ext = FinalTextStreamExtractor()
        raw = '{"action":"tool","name":"list_orders","arguments":{}}'
        out = []
        for ch in raw:
            out.extend(ext.feed(ch))
        assert out == []
        assert ext.emitted_text == ''

    def test_handles_escaped_quotes(self):
        from client.features.communication.assistant.chat.application.json_text_stream import (
            FinalTextStreamExtractor,
        )

        ext = FinalTextStreamExtractor()
        raw = '{"action":"final","text":"Di \\"hola\\""}'
        out = []
        for ch in raw:
            out.extend(ext.feed(ch))
        assert ''.join(out) == 'Di "hola"'


@pytest.mark.unit
class TestChatTurnGates:

    @override_settings(AI_ENABLED=False, AI_PROVIDER='local')
    def test_chat_blocked_when_ai_disabled(self):
        repo = MemoryAssistantRepo()
        registry = ToolRegistry()
        model = ScriptedChatModel(['{"action":"final","text":"no"}'])
        with pytest.raises(ServerException) as exc:
            ChatTurnUseCase(repo, registry, model=model).execute(
                user_id=uuid.uuid4(),
                message='hola',
            )
        assert exc.value.code == AppErrorCode.AI_DISABLED
        assert model.calls == 0

    @override_settings(AI_ENABLED=True, AI_PROVIDER='fake')
    def test_status_reports_enabled(self):
        status = GetAssistantStatusUseCase().execute()
        assert status.enabled is True

    @override_settings(AI_ENABLED=True, AI_PROVIDER='fake')
    def test_chat_turn_persists_with_scripted_model(self):
        repo = MemoryAssistantRepo()
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='noop',
            description='noop',
            parameters_schema={},
            handler=lambda args: '{}',
        ))
        model = ScriptedChatModel(['{"action":"final","text":"Hola operador"}'])
        result = ChatTurnUseCase(repo, registry, model=model).execute(
            user_id=uuid.uuid4(),
            message='hola',
        )
        assert result.reply == 'Hola operador'
        assert model.calls == 1
        roles = [m.role for m in result.messages]
        assert roles.count('user') >= 1
        assert roles.count('assistant') >= 1

    @override_settings(AI_ENABLED=True, AI_PROVIDER='fake')
    def test_failed_agent_does_not_create_conversation(self):
        repo = MemoryAssistantRepo()
        uc = ChatTurnUseCase(repo, ToolRegistry(), model=ScriptedChatModel(['{"action":"final","text":"x"}']))

        class BoomAgent:
            def run(self, *args, **kwargs):
                raise RuntimeError('agent down')

        uc.build_agent = lambda model, run_id=None: BoomAgent()
        with pytest.raises(RuntimeError):
            uc.execute(user_id=uuid.uuid4(), message='hola')
        assert repo.conversations == {}


@pytest.mark.unit
class TestStreamQueueBackpressure:

    def test_enqueue_drops_oldest_under_pressure(self):
        import queue
        import threading
        from client.features.communication.assistant.chat.realtime.consumer import (
            _enqueue_stream_event,
        )

        q = queue.Queue(maxsize=2)
        cancel = threading.Event()
        assert _enqueue_stream_event(q, {'type': 'assistant.token', 'payload': {'text': 'a'}}, cancel=cancel)
        assert _enqueue_stream_event(q, {'type': 'assistant.token', 'payload': {'text': 'b'}}, cancel=cancel)
        assert _enqueue_stream_event(q, {'type': 'assistant.done', 'payload': {}}, cancel=cancel)
        items = []
        while not q.empty():
            items.append(q.get_nowait())
        assert any(i.get('type') == 'assistant.done' for i in items if isinstance(i, dict))

    def test_enqueue_respects_cancel(self):
        import queue
        import threading
        from client.features.communication.assistant.chat.realtime.consumer import (
            _enqueue_stream_event,
        )

        q = queue.Queue(maxsize=1)
        cancel = threading.Event()
        cancel.set()
        assert _enqueue_stream_event(q, {'type': 'assistant.token'}, cancel=cancel) is False
