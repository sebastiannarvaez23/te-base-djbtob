"""Factory y configuración de integraciones."""

from __future__ import annotations

from django.conf import settings

from core.integrations.domain.enums import ConnectorProvider
from core.integrations.domain.interfaces import IConnector, IIdempotencyStore, ISecretStore
from core.integrations.domain.schemas import ConnectionProfile
from core.integrations.infrastructure.idempotency import MemoryIdempotencyStore, RedisIdempotencyStore
from core.integrations.infrastructure.registry import ConnectorRegistry, get_connector_class, register_connector


def is_integrations_enabled() -> bool:
    return bool(getattr(settings, 'INTEGRATIONS_ENABLED', True))


def _register_builtin_connectors() -> None:
    from core.integrations.connectors.app.webhook_inbound import WebhookInboundConnector
    from core.integrations.infrastructure.fake_connector import FakeConnector

    register_connector(ConnectorProvider.FAKE, FakeConnector)
    register_connector(ConnectorProvider.WEBHOOK_INBOUND, WebhookInboundConnector)


_BUILTIN_REGISTERED = False


def _ensure_registered() -> None:
    global _BUILTIN_REGISTERED
    if not _BUILTIN_REGISTERED:
        _register_builtin_connectors()
        _BUILTIN_REGISTERED = True


def get_connector_registry() -> ConnectorRegistry:
    _ensure_registered()
    return ConnectorRegistry()


def get_connector_class_for_provider(
    provider: ConnectorProvider,
    version: str = '1.0',
):
    _ensure_registered()
    return get_connector_class(provider, version)


def get_connector(profile: ConnectionProfile) -> IConnector:
    registry = get_connector_registry()
    cls = registry.resolve(profile.provider, profile.connector_version)
    return cls()


def get_secret_store() -> ISecretStore:
    store_kind = getattr(settings, 'INTEGRATIONS_SECRET_STORE', 'encrypted')
    if store_kind == 'fake':
        from core.integrations.infrastructure.fake_secret_store import FakeSecretStore
        return FakeSecretStore()
    from core.integrations.infrastructure.encrypted_secret_store import EncryptedSecretStore
    return EncryptedSecretStore()


def get_idempotency_store() -> IIdempotencyStore:
    store_kind = getattr(settings, 'INTEGRATIONS_IDEMPOTENCY_STORE', 'redis')
    if store_kind == 'memory':
        return MemoryIdempotencyStore()
    return RedisIdempotencyStore()
