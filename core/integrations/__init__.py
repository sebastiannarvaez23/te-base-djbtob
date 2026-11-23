"""
core/integrations
─────────────────
Módulo transversal de integraciones con sistemas externos (ERPs, proveedores,
aplicaciones del cliente).

Gemelo de ``core/ai/`` y ``core/storage/``: puertos en ``domain/``,
adaptadores en ``connectors/`` e ``infrastructure/``. Ver
``docs/plan-integrations/``.

Uso rápido::

    from core.integrations import get_connector, run_connector_op, OperationContext
    from core.integrations.domain import ConnectionProfile, SyncRequest, SyncDirection

    connector = get_connector(profile)
    ctx = OperationContext(
        connection_id=profile.connection_id,
        tenant_schema=profile.tenant_schema,
        operation='pull_entities',
    )
    result = run_connector_op(connector.pull_entities, sync_request, context=ctx)
"""

from __future__ import annotations

from typing import Callable, TypeVar

from .application.conflict_resolver import ConflictResolver
from .application.connector_runner import ConnectorRunner
from .application.sync_orchestrator import SyncOrchestrator
from .config import (
    get_connector,
    get_connector_registry,
    get_idempotency_store,
    get_secret_store,
    is_integrations_enabled,
)
from .domain import (
    BatchSyncResult,
    ConnectionProfile,
    ConnectionTestResult,
    ConnectorKind,
    ConnectorProvider,
    DryRunResult,
    Environment,
    OperationContext,
    SyncDirection,
    SyncRequest,
    SyncResult,
    SyncStatus,
)
from .infrastructure.fake_connector import FakeConnector
from .infrastructure.registry import ConnectorRegistry

T = TypeVar('T')

_default_runner = ConnectorRunner()


def run_connector_op(
    operation: Callable[..., T],
    request: SyncRequest | ConnectionProfile,
    *,
    context: OperationContext,
    runner: ConnectorRunner | None = None,
) -> T:
    """Ejecuta una operación de conector con idempotencia, timeout y logging."""
    return (runner or _default_runner).run(operation, request, context=context)


__all__ = [
    'BatchSyncResult',
    'ConflictResolver',
    'ConnectionProfile',
    'ConnectionTestResult',
    'ConnectorKind',
    'ConnectorProvider',
    'ConnectorRegistry',
    'ConnectorRunner',
    'DryRunResult',
    'Environment',
    'FakeConnector',
    'OperationContext',
    'SyncDirection',
    'SyncOrchestrator',
    'SyncRequest',
    'SyncResult',
    'SyncStatus',
    'get_connector',
    'get_connector_registry',
    'get_idempotency_store',
    'get_secret_store',
    'is_integrations_enabled',
    'run_connector_op',
]
