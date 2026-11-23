"""Fixtures compartidas para tests de core/integrations."""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.integrations.domain.enums import ConnectorKind, ConnectorProvider, Environment, SyncDirection
from core.integrations.domain.schemas import ConnectionProfile, OperationContext, SyncRequest
from core.integrations.infrastructure.resilience import reset_circuits
from core.integrations.observability import metrics


@pytest.fixture(autouse=True)
def _reset_integration_state():
    metrics.reset_metrics()
    reset_circuits()
    yield
    metrics.reset_metrics()
    reset_circuits()


def make_profile(provider: ConnectorProvider = ConnectorProvider.FAKE) -> ConnectionProfile:
    return ConnectionProfile(
        connection_id=uuid4(),
        tenant_schema='test_tenant',
        provider=provider,
        kind=ConnectorKind.ERP,
        environment=Environment.CLIENT_TEST,
        config={'base_url': 'https://erp.example.com'},
        secrets={'api_key': 'secret-value'},
    )


def make_sync_request(profile: ConnectionProfile | None = None) -> SyncRequest:
    return SyncRequest(
        profile=profile or make_profile(),
        entity='order',
        direction=SyncDirection.INBOUND,
    )


def make_context(profile: ConnectionProfile, operation: str = 'pull_entities') -> OperationContext:
    return OperationContext(
        connection_id=profile.connection_id,
        tenant_schema=profile.tenant_schema,
        operation=operation,
        idempotency_key=f'test-{uuid4()}',
    )
