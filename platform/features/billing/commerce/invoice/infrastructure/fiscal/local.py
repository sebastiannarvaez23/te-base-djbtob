from __future__ import annotations

from typing import Optional

from platform.features.billing.commerce.invoice.domain.fiscal import (
    FiscalIssueRequest,
    FiscalIssueResult,
    FiscalVoidRequest,
    IFiscalInvoicingProvider,
)


class LocalFiscalInvoicingProvider(IFiscalInvoicingProvider):
    """Default: keep base-local invoice numbers; no remote call."""

    def issue(self, request: FiscalIssueRequest) -> Optional[FiscalIssueResult]:
        return None

    def get(self, external_id: str) -> Optional[FiscalIssueResult]:
        return None

    def void(self, request: FiscalVoidRequest) -> Optional[FiscalIssueResult]:
        return None
