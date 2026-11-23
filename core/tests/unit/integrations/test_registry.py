"""Matriz escenarios 1 — Registry."""

import pytest

from core.errors import AppErrorCode
from core.errors.exceptions import ServerException
from core.integrations import ConnectorProvider, FakeConnector, get_connector_registry
from core.integrations.config import get_connector_class_for_provider
from core.integrations.infrastructure import registry as reg_mod


@pytest.mark.unit
class TestRegistry:

    def test_builtin_providers_are_registered(self):
        assert get_connector_class_for_provider(ConnectorProvider.FAKE).__name__ == 'FakeConnector'
        assert get_connector_class_for_provider(ConnectorProvider.WEBHOOK_INBOUND).__name__ == 'WebhookInboundConnector'

    def test_fake_provider_is_registered(self):
        cls = get_connector_registry().resolve(ConnectorProvider.FAKE)
        assert cls is FakeConnector

    def test_unregistered_provider_raises_int_001(self):
        registry = get_connector_registry()
        original = dict(reg_mod._REGISTRY)
        reg_mod._REGISTRY.clear()
        try:
            with pytest.raises(ServerException) as exc:
                registry.resolve(ConnectorProvider.SAP)
            assert exc.value.code == AppErrorCode.INT_CONNECTOR_NOT_FOUND
        finally:
            reg_mod._REGISTRY.update(original)
