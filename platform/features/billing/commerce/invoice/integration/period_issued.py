"""Subscribe invoices to billing-period lifecycle events."""
from platform.features.billing.commerce.invoice.application.bind_period import BindInvoiceToPeriodUseCase
from platform.features.billing.commerce.invoice.infrastructure.repositories import DjangoInvoiceRepository
from platform.features.billing.subscription.subscription.domain.events import PeriodIssued


class PeriodIssuedInvoiceListener:
    def __init__(self, invoice_repo_factory=DjangoInvoiceRepository):
        self._invoice_repo_factory = invoice_repo_factory

    def on_period_issued(self, event: PeriodIssued) -> None:
        if event.charge_id is None:
            return
        BindInvoiceToPeriodUseCase(self._invoice_repo_factory()).execute(
            event.charge_id, event.period_id,
        )
