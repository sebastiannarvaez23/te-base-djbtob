"""FakeConnector — adaptador seguro para tests y desarrollo."""

from __future__ import annotations

from core.integrations.connectors.base import BaseConnector
from core.integrations.domain.enums import (
    ConnectorKind,
    ConnectorProvider,
    SyncDirection,
    SyncStatus,
)
from core.integrations.domain.schemas import (
    ConnectionProfile,
    DryRunResult,
    ExternalEntityRef,
    SyncEntityResult,
    SyncRequest,
    SyncResult,
)


class FakeConnector(BaseConnector):
    provider = ConnectorProvider.FAKE
    kind = ConnectorKind.ERP

    def __init__(
        self,
        *,
        fail_on_test: bool = False,
        pull_count: int = 1,
        push_ok: bool = True,
    ):
        self._fail_on_test = fail_on_test
        self._pull_count = pull_count
        self._push_ok = push_ok

    def _do_test_connection(self, profile: ConnectionProfile) -> str:
        if self._fail_on_test:
            raise ConnectionError('simulated connection failure')
        return f'fake connection ok ({profile.environment.value})'

    def _do_pull(self, request: SyncRequest) -> SyncResult:
        if request.dry_run:
            return self._empty_sync_result()
        entities = [
            SyncEntityResult(
                external_ref=ExternalEntityRef(
                    entity=request.entity,
                    external_id=f'FAKE-{i + 1}',
                ),
                action='create',
            )
            for i in range(self._pull_count)
        ]
        return SyncResult(
            status=SyncStatus.SUCCESS,
            created=len(entities),
            entities=entities,
        )

    def _do_push(self, request: SyncRequest) -> SyncResult:
        if not self._push_ok:
            return SyncResult(status=SyncStatus.FAILED, errors=1)
        payload = request.payload or {}
        items = payload.get('items', [{'external_id': 'OUT-1'}])
        entities = [
            SyncEntityResult(
                external_ref=ExternalEntityRef(
                    entity=request.entity,
                    external_id=str(item.get('external_id', 'OUT')),
                ),
                action='update',
            )
            for item in items
        ]
        return SyncResult(
            status=SyncStatus.SUCCESS,
            updated=len(entities),
            entities=entities,
        )

    def _do_dry_run(self, request: SyncRequest) -> DryRunResult:
        if request.direction == SyncDirection.INBOUND:
            return DryRunResult(would_create=self._pull_count, preview=[{'id': 'FAKE-1'}])
        return DryRunResult(would_update=1, preview=[{'id': 'OUT-1'}])
