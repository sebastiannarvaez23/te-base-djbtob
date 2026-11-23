"""SyncOrchestrator — orquestación batch pull/push en memoria."""

from __future__ import annotations

from uuid import uuid4

from core.integrations.application.connector_runner import ConnectorRunner
from core.integrations.domain.interfaces import IConnector
from core.integrations.domain.schemas import (
    BatchSyncResult,
    ConnectionProfile,
    OperationContext,
    SyncRequest,
)


class SyncOrchestrator:
    """Coordina pull y push sin persistencia (Fase 2 añade SyncRun en BD)."""

    def __init__(self, runner: ConnectorRunner | None = None):
        self._runner = runner or ConnectorRunner()

    def run_batch(
        self,
        connector: IConnector,
        profile: ConnectionProfile,
        *,
        pull_request: SyncRequest | None = None,
        push_request: SyncRequest | None = None,
        request_id: str = '-',
    ) -> BatchSyncResult:
        connection_id = profile.connection_id
        tenant = profile.tenant_schema

        pull_result = None
        if pull_request is not None:
            ctx = OperationContext(
                connection_id=connection_id,
                tenant_schema=tenant,
                operation='pull_entities',
                request_id=request_id,
                idempotency_key=f'pull:{uuid4()}',
            )
            pull_result = self._runner.run(
                connector.pull_entities,
                pull_request,
                context=ctx,
            )

        push_result = None
        if push_request is not None:
            ctx = OperationContext(
                connection_id=connection_id,
                tenant_schema=tenant,
                operation='push_entities',
                request_id=request_id,
                idempotency_key=f'push:{uuid4()}',
            )
            push_result = self._runner.run(
                connector.push_entities,
                push_request,
                context=ctx,
            )

        return BatchSyncResult(pull=pull_result, push=push_result)
