"""Admin list and detail of refund tickets."""
import uuid
from typing import Optional

from core.errors import AppErrorCode, NotFoundException
from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.interfaces import IRefundRequestRepository
from ..domain.schemas import AdminRefundTicketSchema
from core.trace import trace_layer


class ListRefundsUseCase:
    def __init__(self, tickets: IRefundRequestRepository):
        self._tickets = tickets

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self._tickets.list_admin(query)


class GetAdminRefundUseCase:
    def __init__(self, tickets: IRefundRequestRepository):
        self._tickets = tickets

    @trace_layer('application')
    def execute(self, ticket_id: uuid.UUID) -> AdminRefundTicketSchema:
        ticket = self._tickets.get_admin(ticket_id)
        if ticket is None:
            raise NotFoundException(AppErrorCode.RFD_TICKET_NOT_FOUND)
        return ticket
