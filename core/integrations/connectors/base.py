"""BaseConnector — plantilla común para adaptadores."""

from __future__ import annotations

import time
from typing import Any

from core.integrations.domain.enums import ConnectorKind, ConnectorProvider, SyncStatus
from core.integrations.domain.interfaces import IConnector
from core.integrations.domain.schemas import (
    ConnectionProfile,
    ConnectionTestResult,
    DryRunResult,
    SyncRequest,
    SyncResult,
)


class BaseConnector(IConnector):
    """Implementación base con helpers de timing y validación mínima."""

    provider: ConnectorProvider
    kind: ConnectorKind
    version: str = '1.0'

    def test_connection(self, profile: ConnectionProfile) -> ConnectionTestResult:
        started = time.monotonic()
        try:
            message = self._do_test_connection(profile)
            latency = int((time.monotonic() - started) * 1000)
            return ConnectionTestResult(ok=True, message=message, latency_ms=latency)
        except Exception as exc:
            latency = int((time.monotonic() - started) * 1000)
            return ConnectionTestResult(ok=False, message=str(exc), latency_ms=latency)

    def pull_entities(self, request: SyncRequest) -> SyncResult:
        return self._do_pull(request)

    def push_entities(self, request: SyncRequest) -> SyncResult:
        return self._do_push(request)

    def dry_run(self, request: SyncRequest) -> DryRunResult:
        return self._do_dry_run(request)

    def _require_base_url(self, profile: ConnectionProfile) -> str:
        base_url = (profile.config.get('base_url') or '').strip()
        if not base_url:
            raise ValueError('base_url is required in connection config')
        return base_url.rstrip('/')

    def _empty_sync_result(self, **kwargs: Any) -> SyncResult:
        return SyncResult(status=SyncStatus.SUCCESS, **kwargs)

    def _do_test_connection(self, profile: ConnectionProfile) -> str:
        raise NotImplementedError

    def _do_pull(self, request: SyncRequest) -> SyncResult:
        raise NotImplementedError

    def _do_push(self, request: SyncRequest) -> SyncResult:
        raise NotImplementedError

    def _do_dry_run(self, request: SyncRequest) -> DryRunResult:
        raise NotImplementedError
