"""Unit tests — model layer (routing, budgets, openai factory)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings

from core.ai.config import get_chat_model
from core.ai.model_layer.budget import BudgetGuard
from core.ai.model_layer.router import ModelRouter, default_routing_table, resolve_chat_model
from core.ai.model_layer.schemas import ModelRouteDecision, ModelRoutingTable
from core.errors import AppErrorCode, ServerException


@pytest.mark.unit
class TestModelRouter:

    def test_default_table_has_chat(self):
        table = default_routing_table()
        assert 'chat' in table.routes
        assert table.routes['chat'].provider in ('fake', 'local', 'anthropic', 'openai')

    def test_preferred_provider_reorders(self):
        table = ModelRoutingTable(routes={
            'chat': ModelRouteDecision(provider='local', fallbacks=['fake']),
        })
        route = ModelRouter(table).resolve('chat', preferred_provider='openai')
        assert route.provider == 'openai'
        assert 'local' in route.fallbacks

    @override_settings(AI_ENABLED=True, AI_PROVIDER='fake')
    def test_resolve_chat_model_fake(self):
        model, route = resolve_chat_model('chat', preferred_provider='fake')
        assert model.provider_name == 'fake'
        assert route.provider == 'fake'

    @override_settings(AI_ENABLED=True, AI_PROVIDER='openai', AI_API_KEY='')
    def test_resolve_falls_back_when_openai_key_missing(self):
        table = ModelRoutingTable(routes={
            'chat': ModelRouteDecision(provider='openai', fallbacks=['fake']),
        })
        model, route = resolve_chat_model('chat', table=table)
        assert model.provider_name == 'fake'
        assert route.provider == 'fake'

    @override_settings(AI_ENABLED=True, AI_PROVIDER='fake')
    def test_byok_key_not_sent_to_fallback_provider(self, monkeypatch):
        calls = []

        def fake_get(provider, **kwargs):
            calls.append((provider, kwargs.get('api_key')))
            if provider == 'openai':
                raise ServerException(
                    AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                    override_detail='boom',
                )
            from core.ai.infrastructure.genai.fake_provider import FakeChatModel
            return FakeChatModel()

        monkeypatch.setattr('core.ai.config.get_chat_model', fake_get)
        table = ModelRoutingTable(routes={
            'chat': ModelRouteDecision(provider='openai', fallbacks=['fake']),
        })
        model, route = resolve_chat_model(
            'chat',
            table=table,
            api_key='sk-tenant-secret',
            api_key_provider='openai',
        )
        assert model.provider_name == 'fake'
        assert ('openai', 'sk-tenant-secret') in calls
        assert ('fake', None) in calls
        assert route.credential_source == 'platform'


@pytest.mark.unit
class TestBudgetGuard:

    def test_assert_allows_when_no_limit(self):
        BudgetGuard(hourly_budget_usd=None).assert_allowed(
            ModelRouteDecision(provider='fake'),
        )

    def test_assert_raises_when_spent_over_limit(self, monkeypatch):
        guard = BudgetGuard(hourly_budget_usd=Decimal('1.0'))
        monkeypatch.setattr(guard, 'spent_usd', lambda: Decimal('1.5'))
        with pytest.raises(ServerException) as exc:
            guard.assert_allowed(ModelRouteDecision(provider='openai'))
        assert exc.value.code == AppErrorCode.AI_QUOTA_EXCEEDED

    def test_route_max_cost_is_hourly_cap(self, monkeypatch):
        guard = BudgetGuard(hourly_budget_usd=Decimal('10.0'))
        monkeypatch.setattr(guard, 'spent_usd', lambda: Decimal('2.0'))
        with pytest.raises(ServerException) as exc:
            guard.assert_allowed(
                ModelRouteDecision(provider='openai', max_cost_usd=Decimal('1.0')),
            )
        assert exc.value.code == AppErrorCode.AI_QUOTA_EXCEEDED


@pytest.mark.unit
class TestOpenAIFactory:

    @override_settings(AI_ENABLED=True, AI_API_KEY='sk-test')
    def test_get_chat_model_openai(self):
        model = get_chat_model('openai', model_id='gpt-4o-mini')
        assert model.provider_name == 'openai'
        assert model.model_name == 'gpt-4o-mini'

    @override_settings(AI_ENABLED=True, AI_API_KEY='')
    def test_openai_requires_key(self):
        with pytest.raises(ServerException) as exc:
            get_chat_model('openai')
        assert exc.value.code == AppErrorCode.AI_PROVIDER_UNAVAILABLE
