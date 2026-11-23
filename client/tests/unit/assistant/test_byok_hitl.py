"""BYOK credentials + HITL approval store (Harness H4)."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from django.test import override_settings

from core.ai.harness.approval import RunApprovalStore
from core.ai.harness.cancel import RunCancelStore
from core.ids import uuid7
from client.features.communication.assistant.chat.application.agent import AssistantAgent
from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry, ToolSpec
from client.features.communication.assistant.credentials.application.use_cases import (
    ResolveActiveByokUseCase,
)
from client.features.communication.assistant.credentials.domain.schemas import (
    CreateCredentialSchema,
    UpdateCredentialSchema,
)
from client.tests.unit.assistant.test_agent import ScriptedChatModel


@pytest.mark.unit
class TestRunApprovalStore:
    def test_approve_unblocks_waiter(self):
        store = RunApprovalStore(schema='t1', user_id='u1')
        run_id = uuid7()
        store.begin_wait(run_id)
        result = {'decision': None}

        def waiter():
            result['decision'] = store.wait(run_id, timeout_s=2.0)

        t = threading.Thread(target=waiter, daemon=True)
        t.start()
        store.resolve(run_id, 'approved')
        t.join(timeout=3.0)
        assert result['decision'] == 'approved'
        store.clear(run_id)

    def test_cancel_check_returns_none(self):
        store = RunApprovalStore(schema='t1', user_id='u1')
        run_id = uuid7()
        store.begin_wait(run_id)
        cancelled = threading.Event()
        cancelled.set()
        assert store.wait(run_id, timeout_s=1.0, cancel_check=cancelled.is_set) is None
        store.clear(run_id)

    def test_keys_are_scoped_per_user(self):
        run_id = uuid7()
        a = RunApprovalStore(schema='t1', user_id='user-a')
        b = RunApprovalStore(schema='t1', user_id='user-b')
        a.begin_wait(run_id)
        b.begin_wait(run_id)
        a.resolve(run_id, 'approved')
        assert a.wait(run_id, timeout_s=0.5) == 'approved'
        # Other user's waiter is unaffected by foreign resolve.
        assert b.wait(run_id, timeout_s=0.3) is None
        a.clear(run_id)
        b.clear(run_id)


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
@pytest.mark.usefixtures('locmem_access')
class TestHitlAgentApproval:
    def test_tool_waits_then_runs_after_approve(self):
        calls = {'n': 0}

        def handler(args):
            calls['n'] += 1
            assert 'confirmed' not in args
            return '{"ok": true}'

        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='sensitive_action',
            description='Needs confirmation',
            parameters_schema={},
            handler=handler,
            read_only=False,
            requires_confirmation=True,
        ))
        model = ScriptedChatModel([
            '{"action":"tool","name":"sensitive_action","arguments":{}}',
            '{"action":"final","text":"Hecho."}',
        ])
        run_id = uuid7()
        store = RunApprovalStore(schema='t1', user_id='u1')

        def approve_soon():
            import time
            time.sleep(0.15)
            store.resolve(run_id, 'approved')

        threading.Thread(target=approve_soon, daemon=True).start()
        agent = AssistantAgent(
            model,
            registry,
            run_id=run_id,
            approval_store=store,
            approval_timeout_s=3.0,
            require_tool_before_facts=False,
        )
        events = list(agent.iter_events('haz la accion'))
        kinds = [e.get('kind') for e in events]
        assert 'approval_required' in kinds
        assert calls['n'] == 1
        assert any(e.get('kind') == 'final' for e in events)

    def test_model_confirmed_true_does_not_bypass_hitl(self):
        """P0: SLM inventing confirmed=true must still pause for operator."""
        handler = MagicMock(return_value='{"ok": true}')
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='sensitive_action',
            description='Needs confirmation',
            parameters_schema={},
            handler=handler,
            read_only=False,
            requires_confirmation=True,
        ))
        model = ScriptedChatModel([
            '{"action":"tool","name":"sensitive_action","arguments":{"confirmed":true}}',
            '{"action":"final","text":"skip"}',
        ])
        run_id = uuid7()
        store = RunApprovalStore(schema='t1', user_id='u1')

        def deny_soon():
            import time
            time.sleep(0.1)
            store.resolve(run_id, 'denied')

        threading.Thread(target=deny_soon, daemon=True).start()
        agent = AssistantAgent(
            model,
            registry,
            run_id=run_id,
            approval_store=store,
            approval_timeout_s=3.0,
            require_tool_before_facts=False,
        )
        events = list(agent.iter_events('haz la accion'))
        handler.assert_not_called()
        assert any(e.get('kind') == 'approval_required' for e in events)

    def test_tool_denied_skips_handler(self):
        handler = MagicMock(return_value='nope')
        registry = ToolRegistry()
        registry.register(ToolSpec(
            name='sensitive_action',
            description='Needs confirmation',
            parameters_schema={},
            handler=handler,
            read_only=False,
            requires_confirmation=True,
        ))
        model = ScriptedChatModel([
            '{"action":"tool","name":"sensitive_action","arguments":{}}',
            '{"action":"final","text":"Cancelado por el operador."}',
        ])
        run_id = uuid7()
        store = RunApprovalStore(schema='t1', user_id='u1')

        def deny_soon():
            import time
            time.sleep(0.15)
            store.resolve(run_id, 'denied')

        threading.Thread(target=deny_soon, daemon=True).start()
        agent = AssistantAgent(
            model,
            registry,
            run_id=run_id,
            approval_store=store,
            approval_timeout_s=3.0,
            require_tool_before_facts=False,
        )
        events = list(agent.iter_events('haz la accion'))
        handler.assert_not_called()
        assert any(e.get('kind') == 'approval_required' for e in events)
        assert any(
            e.get('kind') == 'tool' and e.get('audit') and e['audit'].error_code == 'APPROVAL_DENIED'
            for e in events
        )


@pytest.mark.unit
class TestByokSchemas:
    def test_create_schema_forbids_extra(self):
        with pytest.raises(Exception):
            CreateCredentialSchema(
                provider='openai',
                api_key='sk-test-key-123456',
                unexpected=True,
            )

    def test_update_requires_at_least_one_field(self):
        with pytest.raises(Exception):
            UpdateCredentialSchema()

    def test_resolve_requires_provider(self):
        repo = MagicMock()
        assert ResolveActiveByokUseCase(repo).execute(None) is None
        repo.get_active_byok.assert_not_called()

    def test_resolve_filters_by_provider(self):
        repo = MagicMock()
        repo.get_active_byok.return_value = None
        ResolveActiveByokUseCase(repo).execute('openai')
        repo.get_active_byok.assert_called_once_with('openai')


@pytest.mark.unit
class TestCancelStoreThrottle:
    def test_redis_poll_throttled(self):
        store = RunCancelStore(schema='t1', user_id='u1', redis_poll_interval_s=10.0)
        run_id = uuid7()
        # Without Redis backend this stays False; throttle path still runs.
        assert store.is_cancelled(run_id) is False
        assert store.is_cancelled(run_id) is False
