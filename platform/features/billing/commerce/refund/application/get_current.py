from uuid import UUID

from ..domain.interfaces import IRefundRequestRepository
from ..domain.schemas import RefundTicketSchema
from core.trace import trace_layer


class GetCurrentRefundUseCase:
    def __init__(self, tickets: IRefundRequestRepository):
        self._tickets = tickets

    @trace_layer('application')
    def execute(self, company_id: UUID) -> RefundTicketSchema | None:
        return self._tickets.get_open(company_id) or self._tickets.get_latest(company_id)
