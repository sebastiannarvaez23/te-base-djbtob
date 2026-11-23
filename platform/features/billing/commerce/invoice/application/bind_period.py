"""Bind an auto-invoice to the CompanySubscription period paid by a charge."""
import uuid

from ..domain.interfaces import IInvoiceRepository
from core.trace import trace_layer


class BindInvoiceToPeriodUseCase:
    def __init__(self, repository: IInvoiceRepository):
        self._repository = repository

    @trace_layer('application')
    def execute(self, charge_id: uuid.UUID, period_id: uuid.UUID) -> int:
        return self._repository.bind_period_for_source_charge(charge_id, period_id)
