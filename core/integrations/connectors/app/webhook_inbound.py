"""WebhookInboundConnector — stub para apps del cliente (inbound hacia la base)."""

from core.integrations.connectors.base import BaseConnector
from core.integrations.domain.enums import ConnectorKind, ConnectorProvider, SyncStatus
from core.integrations.domain.schemas import (
    ConnectionProfile,
    DryRunResult,
    SyncRequest,
    SyncResult,
)


class WebhookInboundConnector(BaseConnector):
    """Fase 1: valida config; procesamiento real en Fase 2 (inbox)."""

    provider = ConnectorProvider.WEBHOOK_INBOUND
    kind = ConnectorKind.APP
    version = '1.0'

    def _do_test_connection(self, profile: ConnectionProfile) -> str:
        path = profile.config.get('webhook_path', '/api/v1/integrations/inbound/')
        return f'webhook endpoint configured at {path}'

    def _do_pull(self, request: SyncRequest) -> SyncResult:
        return SyncResult(status=SyncStatus.SUCCESS, skipped=1)

    def _do_push(self, request: SyncRequest) -> SyncResult:
        return SyncResult(status=SyncStatus.SUCCESS, skipped=1)

    def _do_dry_run(self, request: SyncRequest) -> DryRunResult:
        return DryRunResult(would_skip=1, warnings=['inbound webhooks are push-only'])
