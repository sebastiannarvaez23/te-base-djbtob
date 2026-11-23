"""El chat del assistant está atado a la feature ``assistant.chat``."""

from client.features.communication.assistant.chat.domain.constants import ASSISTANT_CHAT_FEATURE
from client.features.communication.assistant.chat.presentation.api import (
    AssistantChatView,
    AssistantConversationDetailView,
    AssistantConversationListView,
    AssistantStatusView,
)
from client.features.security.lifecycle.registration.feature_registry import FEATURE_REGISTRY


def test_chat_feature_is_in_registry():
    keys = {entry['key'] for entry in FEATURE_REGISTRY}
    assert ASSISTANT_CHAT_FEATURE in keys
    entry = next(e for e in FEATURE_REGISTRY if e['key'] == ASSISTANT_CHAT_FEATURE)
    assert entry['module'] == 'assistant'


def test_chat_view_requires_subscription_feature():
    assert AssistantChatView.subscription_functionality == ASSISTANT_CHAT_FEATURE


def test_read_views_skip_quota_chat_view_enforces_it():
    assert getattr(AssistantStatusView, 'subscription_check_quota', True) is False
    assert getattr(AssistantConversationListView, 'subscription_check_quota', True) is False
    assert getattr(AssistantConversationDetailView, 'subscription_check_quota', True) is False
    assert getattr(AssistantChatView, 'subscription_check_quota', True) is True


def test_ws_connect_skips_quota_check():
    from unittest.mock import MagicMock, patch

    from client.features.communication.assistant.chat.realtime.consumer import AssistantChatConsumer

    consumer = AssistantChatConsumer()
    consumer.user = MagicMock()
    company = MagicMock()
    consumer.user.company = company
    allowed = MagicMock()
    allowed.is_allowed = True

    with patch(
        'client.features.communication.assistant.chat.realtime.consumer.AccessChecker'
    ) as MockChecker:
        MockChecker.check_feature.return_value = allowed
        assert consumer._has_chat_access() is True
        MockChecker.check_feature.assert_called_once_with(
            company, ASSISTANT_CHAT_FEATURE, check_quota=False,
        )


def test_ws_connect_without_company_is_denied():
    from unittest.mock import MagicMock

    from client.features.communication.assistant.chat.realtime.consumer import AssistantChatConsumer

    consumer = AssistantChatConsumer()
    consumer.user = MagicMock()
    consumer.user.company = None
    assert consumer._has_chat_access() is False


def test_chat_turn_body_rejects_oversized_message():
    from core.ai.assistant_catalog import ASSISTANT_MAX_MESSAGE_MAX
    from core.validators import ValidationCode
    from client.features.communication.assistant.chat.presentation.bodies import ChatTurnBody

    # Absolute HTTP ceiling (admin may raise policy up to this); policy enforces lower.
    body = ChatTurnBody({'message': 'x' * (ASSISTANT_MAX_MESSAGE_MAX + 1)})
    ok, errors = body.validate()
    assert ok is False
    assert any(e.field == 'message' and e.code == ValidationCode.MAX_LENGTH for e in errors)


def test_chat_turn_body_rejects_unknown_fields():
    from core.validators import ValidationCode
    from client.features.communication.assistant.chat.presentation.bodies import ChatTurnBody

    body = ChatTurnBody({'message': 'hola', 'extra': 1})
    ok, errors = body.validate()
    assert ok is False
    assert any(e.code == ValidationCode.UNKNOWN_FIELD for e in errors)


def test_chat_turn_body_accepts_ui_context():
    from client.features.communication.assistant.chat.presentation.bodies import ChatTurnBody

    body = ChatTurnBody({
        'message': 'what is the status?',
        'ui_context': {
            'route': '/warehouse/orders',
            'module_code': 'orders',
            'module_name': 'Orders',
            'feature_key': 'orders.view-status',
            'page_section': 'list',
            'page_section_label': 'Listado',
            'module_purpose': 'Gestiona pedidos de salida.',
        },
    })
    ok, errors = body.validate()
    assert ok is True, errors
    ctx = body.validated_data['ui_context']
    assert ctx['route'] == '/warehouse/orders'
    assert ctx['feature_key'] == 'orders.view-status'
    assert ctx['page_section_label'] == 'Listado'
    assert ctx['module_purpose'] == 'Gestiona pedidos de salida.'


def test_chat_turn_body_rejects_unknown_ui_context_field():
    from core.validators import ValidationCode
    from client.features.communication.assistant.chat.presentation.bodies import ChatTurnBody

    body = ChatTurnBody({
        'message': 'hola',
        'ui_context': {'route': '/x', 'hack': True},
    })
    ok, errors = body.validate()
    assert ok is False
    assert any(e.code == ValidationCode.UNKNOWN_FIELD for e in errors)


def test_format_ui_context_for_prompt():
    from client.features.communication.assistant.chat.application.ui_context import format_ui_context_for_prompt

    assert format_ui_context_for_prompt(None) == ''
    assert format_ui_context_for_prompt({}) == ''
    block = format_ui_context_for_prompt({
        'route': '/warehouse/orders',
        'module_name': 'Orders',
        'feature_key': 'orders.view-status',
        'page_section': 'list',
        'page_section_label': 'Listado',
        'module_purpose': 'Gestiona pedidos de salida.',
    })
    assert 'Operator screen context' in block
    assert 'Visible to operator' in block
    assert 'Module: Orders' in block
    assert 'Tab: Listado' in block
    assert 'Purpose: Gestiona pedidos de salida.' in block
    assert 'Internal only' in block
    assert 'Route: /warehouse/orders' in block
    assert 'Feature: orders.view-status' in block
    assert 'Page section key: list' in block


def test_is_orientation_question():
    from client.features.communication.assistant.chat.application.orientation import is_orientation_question

    assert is_orientation_question('En que pantalla estoy en estos momentos?')
    assert is_orientation_question('En que modulo me encuentro actualmente?')
    assert is_orientation_question('En que pestaña me encuentro y para que sirve este modulo?')
    assert is_orientation_question('Where am I right now?')
    assert is_orientation_question('Which tab am I on?')
    assert not is_orientation_question('Cuantas ordenes hay en draft?')
    assert not is_orientation_question('List references for type BOX')


def test_agent_includes_ui_context_in_system_prompt():
    from client.features.communication.assistant.chat.application.agent import AssistantAgent
    from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry
    from client.tests.unit.assistant.test_agent import ScriptedChatModel

    class CaptureModel(ScriptedChatModel):
        last_system = ''

        def _generate(self, prompt):
            type(self).last_system = prompt.system or ''
            return super()._generate(prompt)

    model = CaptureModel(['{"action":"final","text":"ok"}'])
    agent = AssistantAgent(
        model,
        ToolRegistry(),
        require_tool_before_facts=False,
        ui_context={
            'route': '/warehouse/orders',
            'page_section': 'list',
            'module_name': 'Orders',
        },
    )
    agent.run('status?')
    assert 'Route: /warehouse/orders' in CaptureModel.last_system
    assert 'Page section key: list' in CaptureModel.last_system
    assert 'Module: Orders' in CaptureModel.last_system


def test_orientation_turn_disables_warehouse_tools():
    from client.features.communication.assistant.chat.application.agent import AssistantAgent
    from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry, ToolSpec
    from client.tests.unit.assistant.test_agent import ScriptedChatModel

    called = {'n': 0}

    def boom(_args):
        called['n'] += 1
        return {'Draft': 0, 'Confirmed': 1}

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name='get_order_indicators',
        description='Order KPIs by status',
        parameters_schema={},
        handler=boom,
    ))

    class CaptureModel(ScriptedChatModel):
        last_system = ''
        prompts = []

        def _generate(self, prompt):
            type(self).last_system = prompt.system or ''
            type(self).prompts.append(prompt)
            return super()._generate(prompt)

    # First reply wrongly asks for a tool; second must be final after hard gate.
    model = CaptureModel([
        '{"action":"tool","name":"get_order_indicators","arguments":{}}',
        '{"action":"final","text":"Estás en el módulo Inventarios, pestaña Referencias."}',
    ])
    agent = AssistantAgent(
        model,
        registry,
        require_tool_before_facts=True,
        ui_context={
            'module_name': 'Inventarios',
            'page_section_label': 'Referencias',
            'module_purpose': 'Administra el maestro de productos.',
            'route': '/warehouse/inventories',
        },
    )
    reply, audits, _, _cancelled = agent.run('En que pantalla estoy en estos momentos?')
    assert 'Inventarios' in reply
    assert 'Referencias' in reply
    assert called['n'] == 0
    assert any(a.error_code == 'ORIENTATION_NO_TOOLS' for a in audits)
    assert 'orientation question' in CaptureModel.last_system.lower()
    assert 'get_order_indicators' not in CaptureModel.prompts[0].system


def test_non_orientation_can_still_use_tools():
    from client.features.communication.assistant.chat.application.agent import AssistantAgent
    from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry, ToolSpec
    from client.tests.unit.assistant.test_agent import ScriptedChatModel

    def indicators(_args):
        return {'Draft': 0, 'Confirmed': 2}

    registry = ToolRegistry()
    registry.register(ToolSpec(
        name='get_order_indicators',
        description='Order KPIs by status',
        parameters_schema={},
        handler=indicators,
    ))
    model = ScriptedChatModel([
        '{"action":"tool","name":"get_order_indicators","arguments":{}}',
        '{"action":"final","text":"Confirmados: 2."}',
    ])
    agent = AssistantAgent(
        model,
        registry,
        require_tool_before_facts=True,
        ui_context={'module_name': 'Orders', 'route': '/warehouse/orders'},
    )
    reply, audits, _, _cancelled = agent.run('Cuantas ordenes confirmadas hay?')
    assert '2' in reply
    assert len(audits) == 1
    assert audits[0].success is True
    assert audits[0].tool_name == 'get_order_indicators'
