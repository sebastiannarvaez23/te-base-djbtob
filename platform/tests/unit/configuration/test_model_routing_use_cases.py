"""Unit tests — platform AI model routing admin use cases."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.ai.model_layer.schemas import ModelRouteDecision, ModelRoutingTable
from core.ai.model_layer.catalog import AI_CAPABILITIES
from core.errors import ValidationAppException

from platform.features.configuration.ai.model_routing.application.use_cases import (
    GetModelRoutingAdminUseCase,
    UpdateModelRoutingAdminUseCase,
)


class MemoryRoutingRepo:
    def __init__(self):
        self.table = ModelRoutingTable(routes={
            cap: ModelRouteDecision(provider='fake') for cap in AI_CAPABILITIES
        })
        self.updated_at = None

    def get_table(self):
        return self.table

    def save_table(self, table):
        self.table = table
        return table

    def get_updated_at(self):
        return self.updated_at


class FakeHealth:
    def probe(self, provider: str) -> str:
        return 'ok' if provider == 'fake' else 'unknown'


@pytest.mark.unit
class TestModelRoutingUseCases:

    def test_get_returns_all_capabilities(self):
        result = GetModelRoutingAdminUseCase(MemoryRoutingRepo(), FakeHealth()).execute()
        assert len(result.routes) == len(AI_CAPABILITIES)
        assert {r.capability for r in result.routes} == set(AI_CAPABILITIES)

    def test_update_persists_budget_and_routes(self):
        repo = MemoryRoutingRepo()
        body = {
            'hourly_budget_usd': 2.5,
            'routes': [
                {
                    'capability': cap,
                    'provider': 'fake',
                    'model_id': '',
                    'credential_source': 'platform',
                    'fallbacks': [],
                    'max_tokens': 512,
                    'timeout_s': 30.0,
                }
                for cap in AI_CAPABILITIES
            ],
        }
        result = UpdateModelRoutingAdminUseCase(repo, FakeHealth()).execute(body)
        assert result.hourly_budget_usd == Decimal('2.5')
        assert all(r.max_tokens == 512 for r in result.routes)

    def test_update_rejects_incomplete_catalog(self):
        with pytest.raises(ValidationAppException):
            UpdateModelRoutingAdminUseCase(MemoryRoutingRepo(), FakeHealth()).execute({
                'routes': [{'capability': 'chat', 'provider': 'fake'}],
            })
