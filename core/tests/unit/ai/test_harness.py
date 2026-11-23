"""Unit tests — core/ai/harness (Agent Loop foundations)."""

from __future__ import annotations

import threading
import uuid

import pytest
from django.conf import settings
from django.test import override_settings

from core.ai.harness.cancel import RunCancelStore, is_cancelled
from core.ai.harness.environment import CapabilityBoundary
from core.ai.harness.extensions import HookBus, HookPoint
from core.ai.harness.facts_gate import enforce_tool_before_facts, looks_like_warehouse_fact
from core.ai.harness.parse import chunk_text, parse_agent_action


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
        assert action is not None
        assert action.action == 'final'
        assert action.text == 'Hola'

    def test_chunk_text_covers_full(self):
        text = 'abcdefghij'
        assert ''.join(chunk_text(text, size=3)) == text


@pytest.mark.unit
class TestFactsGate:

    def test_looks_like_warehouse_fact_with_digits(self):
        assert looks_like_warehouse_fact('Hay 12 pedidos en stock')

    def test_chitchat_is_not_fact(self):
        assert not looks_like_warehouse_fact('Hola, ¿en qué puedo ayudarte?')

    def test_enforce_replaces_facts_without_tool(self):
        out = enforce_tool_before_facts(
            'Tienes 5 bodegas operando',
            require_tool_before_facts=True,
            orientation=False,
            had_successful_tool=False,
            out_of_scope_message='OUT',
        )
        assert out == 'OUT'

    def test_enforce_keeps_facts_after_tool(self):
        text = 'Tienes 5 bodegas operando'
        out = enforce_tool_before_facts(
            text,
            require_tool_before_facts=True,
            orientation=False,
            had_successful_tool=True,
            out_of_scope_message='OUT',
        )
        assert out == text

    def test_enforce_keeps_orientation(self):
        text = 'Estás en el módulo Inventarios'
        out = enforce_tool_before_facts(
            text,
            require_tool_before_facts=True,
            orientation=True,
            had_successful_tool=False,
            out_of_scope_message='OUT',
        )
        assert out == text

    def test_enforce_keeps_chitchat(self):
        text = 'Hola operador'
        out = enforce_tool_before_facts(
            text,
            require_tool_before_facts=True,
            orientation=False,
            had_successful_tool=False,
            out_of_scope_message='OUT',
        )
        assert out == text


@pytest.mark.unit
class TestCapabilityBoundary:

    def test_deny_by_default(self):
        boundary = CapabilityBoundary(['list_orders'])
        assert boundary.allows('list_orders')
        assert not boundary.allows('drop_database')


@pytest.mark.unit
class TestHookBus:

    def test_emits_in_order(self):
        bus = HookBus(strict=True)
        seen = []
        bus.register(HookPoint.BEFORE_RUN, lambda **kw: seen.append('a'))
        bus.register(HookPoint.BEFORE_RUN, lambda **kw: seen.append('b'))
        bus.emit(HookPoint.BEFORE_RUN)
        assert seen == ['a', 'b']

    def test_best_effort_swallows_hook_errors(self):
        bus = HookBus(strict=False)
        bus.register(HookPoint.ON_ERROR, lambda **kw: (_ for _ in ()).throw(RuntimeError('x')))
        bus.emit(HookPoint.ON_ERROR)  # must not raise


@pytest.fixture
def locmem_access():
    caches_cfg = {alias: dict(conf) for alias, conf in settings.CACHES.items()}
    caches_cfg['access'] = {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unit-access',
    }
    with override_settings(CACHES=caches_cfg):
        yield


@pytest.mark.unit
class TestCancel:

    def test_local_event(self):
        ev = threading.Event()
        assert not is_cancelled(local=ev)
        ev.set()
        assert is_cancelled(local=ev)

    def test_store_roundtrip(self, locmem_access):
        store = RunCancelStore()
        run_id = uuid.uuid4()
        assert not store.is_cancelled(run_id)
        store.request_cancel(run_id)
        # Cache may be LocMem or Redis; either way set/get should work in tests.
        assert store.is_cancelled(run_id)
        store.clear(run_id)
        assert not store.is_cancelled(run_id)
