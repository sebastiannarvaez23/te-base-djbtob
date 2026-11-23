"""Unit tests — configuración de plataforma del assistant."""
from inspect import unwrap
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.test import override_settings

from core.ai.assistant_catalog import ASSISTANT_TOOL_KEYS
from core.ai.assistant_policy import AssistantRuntimePolicy, default_assistant_policy
from core.ai.health import RuntimeHealthProbe, probe_inference_health
from core.errors.codes import AppErrorCode
from core.errors.exceptions import ServerException, ValidationAppException
from core.validators.core import ValidationCode
from client.features.communication.assistant.chat.application.agent import AssistantAgent
from client.features.communication.assistant.chat.application.message import normalize_chat_message
from client.features.communication.assistant.chat.application.use_cases import ChatTurnStreamUseCase, ChatTurnUseCase
from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry
from client.features.communication.assistant.chat.infrastructure.tools import build_default_tool_registry
from client.tests.unit.assistant.test_agent import MemoryAssistantRepo, ScriptedChatModel
from platform.features.configuration.assistant.assistant.application.use_cases import (
    GetAssistantAdminSettingsUseCase,
    LoadAssistantRuntimePolicyUseCase,
    UpdateAssistantAdminSettingsUseCase,
)
from platform.features.configuration.assistant.assistant.domain.mapping import merge_tool_map
from platform.features.configuration.assistant.assistant.domain.schemas import (
    AssistantSettingsPersistSchema,
    AssistantUsageSchema,
)
from platform.features.configuration.assistant.assistant.infrastructure.adapters import (
    NullAssistantUsageReader,
    StaticRuntimeHealthProbe,
)
from platform.features.configuration.assistant.assistant.presentation.bodies import (
    UpdateAssistantSettingsBody,
)

pytestmark = pytest.mark.unit


def _persist(**overrides) -> AssistantSettingsPersistSchema:
    data = dict(
        enabled=True,
        provider='local',
        max_message_chars=4000,
        max_agent_steps=4,
        history_turns=8,
        out_of_scope_message='',
        require_tool_before_facts=True,
        enabled_tools=merge_tool_map(None),
    )
    data.update(overrides)
    return AssistantSettingsPersistSchema(**data)


def _all_tools(*, disabled: set[str] | None = None) -> list[dict]:
    off = disabled or set()
    return [{'key': key, 'enabled': key not in off} for key in ASSISTANT_TOOL_KEYS]


def _patch_body(**overrides) -> dict:
    data = {
        'enabled': True,
        'provider': 'local',
        'max_message_chars': 4000,
        'max_agent_steps': 4,
        'history_turns': 8,
        'out_of_scope_message': '',
        'require_tool_before_facts': True,
        'tools': _all_tools(),
    }
    data.update(overrides)
    return data


class TestMergeTools(TestCase):

    def test_fills_catalog_defaults(self):
        merged = merge_tool_map({'list_orders': False, 'unknown': True})
        self.assertEqual(merged, {})


class TestLoadPolicy(TestCase):

    def test_defaults_when_missing(self):
        repo = MagicMock()
        repo.get.return_value = None
        uc = LoadAssistantRuntimePolicyUseCase(repo)
        policy = unwrap(uc.execute)(uc)
        self.assertTrue(policy.enabled)
        self.assertEqual(policy.enabled_tool_keys, ())

    def test_disables_tools(self):
        repo = MagicMock()
        repo.get.return_value = _persist(enabled_tools={'list_orders': False})
        uc = LoadAssistantRuntimePolicyUseCase(repo)
        policy = unwrap(uc.execute)(uc)
        self.assertEqual(policy.enabled_tool_keys, ())


class TestUpdateSettings(TestCase):

    def test_rejects_unknown_tool(self):
        repo = MagicMock()
        with self.assertRaises(ValidationAppException) as ctx:
            UpdateAssistantAdminSettingsUseCase(
                repo, StaticRuntimeHealthProbe('ok'), NullAssistantUsageReader(),
            ).execute(_patch_body(tools=[
                *[{'key': k, 'enabled': True} for k in ASSISTANT_TOOL_KEYS[:-1]],
                {'key': 'drop_table', 'enabled': True},
            ]))
        self.assertEqual(ctx.exception.code, AppErrorCode.AI_UNKNOWN_TOOL)

    def test_rejects_named_tool_when_catalog_is_empty(self):
        repo = MagicMock()
        with self.assertRaises(ValidationAppException) as ctx:
            UpdateAssistantAdminSettingsUseCase(
                repo, StaticRuntimeHealthProbe('ok'), NullAssistantUsageReader(),
            ).execute(_patch_body(tools=[
                {'key': 'list_orders', 'enabled': True},
                {'key': 'list_orders', 'enabled': False},
            ]))
        self.assertEqual(ctx.exception.code, AppErrorCode.AI_UNKNOWN_TOOL)

    def test_empty_catalog_accepts_no_tools(self):
        repo = MagicMock()
        repo.save.return_value = _persist()
        result = UpdateAssistantAdminSettingsUseCase(
            repo, StaticRuntimeHealthProbe('ok'), NullAssistantUsageReader(),
        ).execute(_patch_body(tools=[]))
        self.assertTrue(result.enabled)
        self.assertEqual(result.tools, [])

    def test_saves_without_usage_scan(self):
        repo = MagicMock()
        saved = _persist(enabled=False, max_agent_steps=2)
        repo.save.return_value = saved
        usage = MagicMock()
        usage.collect_24h.return_value = AssistantUsageSchema()
        result = UpdateAssistantAdminSettingsUseCase(
            repo, StaticRuntimeHealthProbe('ok'), usage,
        ).execute(_patch_body(enabled=False, max_agent_steps=2))
        self.assertFalse(result.enabled)
        self.assertEqual(result.max_agent_steps, 2)
        self.assertEqual(result.runtime_health, 'ok')
        usage.collect_24h.assert_called_once()
        repo.save.assert_called_once()

    def test_get_uses_defaults_when_empty(self):
        repo = MagicMock()
        repo.get.return_value = None
        usage = MagicMock()
        usage.collect_24h.return_value = AssistantUsageSchema(messages_24h=3)
        result = GetAssistantAdminSettingsUseCase(
            repo, StaticRuntimeHealthProbe('down'), usage,
        ).execute()
        self.assertTrue(result.enabled)
        self.assertEqual(result.usage.messages_24h, 3)
        self.assertEqual(result.runtime_health, 'down')
        self.assertEqual(result.tools, [])


class TestUpdateSettingsBody(TestCase):

    def test_rejects_unknown_field(self):
        body = UpdateAssistantSettingsBody({**_patch_body(), 'extra': True})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(e.code == ValidationCode.UNKNOWN_FIELD for e in errors))

    def test_rejects_out_of_range_chars(self):
        body = UpdateAssistantSettingsBody(_patch_body(max_message_chars=50))
        ok, errors = body.validate()
        self.assertFalse(ok)

    def test_rejects_unknown_provider(self):
        body = UpdateAssistantSettingsBody(_patch_body(provider='not-a-provider'))
        ok, errors = body.validate()
        self.assertFalse(ok)

    def test_accepts_openai_provider(self):
        body = UpdateAssistantSettingsBody(_patch_body(provider='openai'))
        ok, errors = body.validate()
        self.assertTrue(ok, errors)

    def test_rejects_unknown_tool_key(self):
        body = UpdateAssistantSettingsBody(_patch_body(
            tools=[{'key': 'hack', 'enabled': True}],
        ))
        ok, errors = body.validate()
        self.assertFalse(ok, errors)

    def test_accepts_valid_payload(self):
        body = UpdateAssistantSettingsBody(_patch_body())
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(len(body.validated_data['tools']), len(ASSISTANT_TOOL_KEYS))


class TestHealthProbe(TestCase):

    def test_fake_is_ok(self):
        self.assertEqual(probe_inference_health('fake'), 'ok')

    def test_anthropic_without_key_is_unknown(self):
        with override_settings(AI_API_KEY=''):
            self.assertEqual(RuntimeHealthProbe().probe('anthropic'), 'unknown')

    @patch('core.ai.health.urllib.request.urlopen')
    def test_local_down_on_network_error(self, mock_open):
        mock_open.side_effect = OSError('down')
        self.assertEqual(RuntimeHealthProbe().probe('local'), 'down')


class TestChatRespectsPolicy(TestCase):

    def test_blocked_when_platform_disabled(self):
        base = default_assistant_policy()
        policy = AssistantRuntimePolicy(
            enabled=False,
            provider=base.provider,
            max_message_chars=base.max_message_chars,
            max_agent_steps=base.max_agent_steps,
            history_turns=base.history_turns,
            out_of_scope_message='',
            require_tool_before_facts=True,
            enabled_tool_keys=base.enabled_tool_keys,
        )
        model = ScriptedChatModel(['{"action":"final","text":"no"}'])
        with self.assertRaises(ServerException) as ctx:
            ChatTurnUseCase(
                MemoryAssistantRepo(), ToolRegistry(), model=model, policy=policy,
            ).execute(user_id=uuid4(), message='hola')
        self.assertEqual(ctx.exception.code, AppErrorCode.AI_DISABLED)
        self.assertEqual(model.calls, 0)

    def test_message_exceeds_policy_limit(self):
        base = default_assistant_policy()
        policy = AssistantRuntimePolicy(
            enabled=True,
            provider=base.provider,
            max_message_chars=10,
            max_agent_steps=base.max_agent_steps,
            history_turns=base.history_turns,
            out_of_scope_message='',
            require_tool_before_facts=True,
            enabled_tool_keys=base.enabled_tool_keys,
        )
        with self.assertRaises(ValidationAppException):
            normalize_chat_message(policy, 'x' * 11)

    def test_stream_errors_when_platform_disabled(self):
        base = default_assistant_policy()
        policy = AssistantRuntimePolicy(
            enabled=False,
            provider=base.provider,
            max_message_chars=base.max_message_chars,
            max_agent_steps=base.max_agent_steps,
            history_turns=base.history_turns,
            out_of_scope_message='',
            require_tool_before_facts=True,
            enabled_tool_keys=base.enabled_tool_keys,
        )
        model = ScriptedChatModel(['{"action":"final","text":"x"}'])
        events = list(
            ChatTurnStreamUseCase(
                MemoryAssistantRepo(), ToolRegistry(), model=model, policy=policy,
            ).execute(user_id=uuid4(), message='hola'),
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'assistant.error')
        self.assertEqual(events[0]['payload']['code'], 'AI_006')
        self.assertEqual(model.calls, 0)

    def test_require_tool_is_in_system_prompt(self):
        registry = ToolRegistry()
        policy = default_assistant_policy()

        class CaptureModel(ScriptedChatModel):
            last_system = ''

            def _generate(self, prompt):
                type(self).last_system = prompt.system or ''
                return super()._generate(prompt)

        model = CaptureModel(['{"action":"final","text":"Hola operador"}'])
        result = ChatTurnUseCase(
            MemoryAssistantRepo(), registry, model=model, policy=policy,
        ).execute(user_id=uuid4(), message='hola')
        self.assertEqual(result.reply, 'Hola operador')
        self.assertIn('successful tool', CaptureModel.last_system)
        self.assertIn(policy.out_of_scope_text, CaptureModel.last_system)

    def test_filtered_registry_omits_disabled_tools(self):
        registry = build_default_tool_registry(
            enabled_keys=('get_reference',),
        )
        self.assertEqual(registry.names(), [])


class TestAgentHistoryWindow(TestCase):

    def test_max_steps_from_constructor(self):
        registry = ToolRegistry()
        model = ScriptedChatModel([
            '{"action":"tool","name":"missing","arguments":{}}',
            '{"action":"tool","name":"missing","arguments":{}}',
            '{"action":"final","text":"ok"}',
        ])
        agent = AssistantAgent(
            model, registry, max_steps=1, require_tool_before_facts=False,
        )
        text, audits, _, _cancelled = agent.run('hola')
        self.assertEqual(model.calls, 1)
        self.assertTrue(text)
        self.assertEqual(len(audits), 1)
