from __future__ import annotations

import logging
from typing import Any, Optional

from platform.features.billing.commerce.invoice.domain.fiscal import (
    FiscalIssueRequest,
    FiscalIssueResult,
    FiscalRejectedError,
    FiscalTransientError,
    FiscalVoidRequest,
    IFiscalInvoicingProvider,
)

logger = logging.getLogger('billing.invoice.fiscal')

_ALREADY_EXISTS_CODES = frozenset({'FIN_001', 'FIN_INVOICE_EXISTS'})
# Auth / permission failures are configuration problems: keep retrying (and
# alerting) instead of marking the fiscal document rejected.
_RETRYABLE_AUTH_STATUSES = frozenset({401, 403})


def classify_remote_error(exc: BaseException) -> Exception:
    """Map client exceptions to the fiscal port's transient / rejected errors."""
    from necore.ecosystem.exceptions import CircuitOpenError, RemoteEcosystemError

    if isinstance(exc, CircuitOpenError):
        return FiscalTransientError(
            'Neurana circuit open', code='ECO_012', retry_after=exc.retry_after, circuit_open=True,
        )
    if isinstance(exc, RemoteEcosystemError):
        code = exc.remote_code or 'ECO_009'
        if exc.is_transient or exc.remote_http_status in _RETRYABLE_AUTH_STATUSES:
            return FiscalTransientError(str(exc), code=code, retry_after=exc.retry_after)
        return FiscalRejectedError(str(exc), code=code)
    return FiscalTransientError(str(exc) or exc.__class__.__name__, code='ECO_013')


class NeuranaFiscalInvoicingProvider(IFiscalInvoicingProvider):
    """POST/GET ecosystem invoices via the shared ``EcosystemClient``."""

    def __init__(self, client=None):
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        from platform.features.billing.commerce.invoice.infrastructure.fiscal.ecosystem_client import (
            get_ecosystem_client,
        )

        return get_ecosystem_client()

    def issue(self, request: FiscalIssueRequest) -> Optional[FiscalIssueResult]:
        from necore.ecosystem.contracts import IssueInvoiceV1

        try:
            payload = IssueInvoiceV1.model_validate({
                'external_ref': request.external_ref,
                'issue_date': request.issue_date,
                'currency': request.currency,
                'customer': request.customer,
                'lines': request.lines,
                'payment': request.payment or None,
                'metadata': {
                    **(request.metadata or {}),
                    'wa_invoice_id': str(request.invoice_id),
                },
            })
        except ValueError as exc:
            raise FiscalRejectedError(str(exc), code='ECO_016') from exc

        client = self._get_client()
        try:
            data = client.create_invoice(payload, idempotency_key=str(request.charge_id))
        except Exception as exc:  # noqa: BLE001 — classified below
            recovered = self._recover_existing(client, request.external_ref, exc)
            if recovered is not None:
                return recovered
            raise classify_remote_error(exc) from exc
        return self._map(data)

    def get(self, external_id: str) -> Optional[FiscalIssueResult]:
        try:
            return self._map(self._get_client().get_invoice(external_id))
        except Exception:  # noqa: BLE001 — reconciliation read is best-effort
            logger.warning('Neurana fiscal get failed external_id=%s', external_id)
            return None

    def void(self, request: FiscalVoidRequest) -> Optional[FiscalIssueResult]:
        from necore.ecosystem.contracts import VoidInvoiceV1

        try:
            data = self._get_client().void_invoice(
                request.external_id,
                reason=VoidInvoiceV1(reason=request.reason or '').reason,
                idempotency_key=request.idempotency_key or f'void:{request.external_id}',
            )
        except Exception as exc:  # noqa: BLE001
            raise classify_remote_error(exc) from exc
        return self._map(data)

    def _recover_existing(self, client, external_ref: str, exc: BaseException) -> Optional[FiscalIssueResult]:
        if (getattr(exc, 'remote_code', '') or '') not in _ALREADY_EXISTS_CODES:
            return None
        try:
            rows = client.list_invoices(external_ref=external_ref)
        except Exception:  # noqa: BLE001
            logger.warning('Neurana fiscal recover failed external_ref=%s', external_ref)
            return None
        if isinstance(rows, list) and rows:
            return self._map(rows[0])
        return None

    def _map(self, data: Any) -> Optional[FiscalIssueResult]:
        if not isinstance(data, dict):
            return None
        return FiscalIssueResult(
            external_id=str(data.get('id') or ''),
            fiscal_number=str(data.get('number') or ''),
            fiscal_status=str(data.get('status') or 'pending'),
            fiscal_payload=dict(data),
        )
