from __future__ import annotations

from typing import Optional
from uuid import UUID

from platform.features.billing.commerce.fiscal_outbox.domain.interfaces import (
    IFiscalDocumentGateway,
)
from platform.features.billing.commerce.invoice.application.fiscal_issue import (
    IssueFiscalInvoiceUseCase,
    VoidFiscalInvoiceUseCase,
    mark_fiscal_rejected,
)


class InvoiceFiscalDocumentGateway(IFiscalDocumentGateway):
    """Adapter onto the invoice entity's fiscal use cases."""

    def __init__(self, provider=None):
        self._provider = provider

    def issue(self, invoice_id: UUID, charge_id: Optional[UUID]) -> str:
        outcome = IssueFiscalInvoiceUseCase(self._provider).execute(invoice_id, charge_id)
        return str(outcome.get('status') or '')

    def void(
        self, invoice_id: UUID, *, reason: str, idempotency_key: str, issue_abandoned: bool,
    ) -> str:
        outcome = VoidFiscalInvoiceUseCase(self._provider).execute(
            invoice_id,
            reason=reason,
            idempotency_key=idempotency_key,
            issue_abandoned=issue_abandoned,
        )
        return str(outcome.get('status') or '')

    def mark_rejected(self, invoice_id: UUID, *, error_code: str) -> None:
        mark_fiscal_rejected(invoice_id, error_code=error_code)
