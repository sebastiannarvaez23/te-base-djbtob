"""Admin rejection: close the ticket without switching plan or paying out."""
import logging
import uuid

from core.errors import AppErrorCode, ConflictException, NotFoundException

from ..domain.interfaces import (
    ICompanyRecipientLookup,
    IRefundNotifier,
    IRefundRequestRepository,
)
from ..domain.schemas import RefundNotification, RefundTicketSchema
from core.trace import trace_layer

logger = logging.getLogger('billing.refund')


class RejectRefundUseCase:
    def __init__(
        self,
        tickets: IRefundRequestRepository,
        notifier: IRefundNotifier,
        recipients: ICompanyRecipientLookup,
    ):
        self._tickets = tickets
        self._notifier = notifier
        self._recipients = recipients

    @trace_layer('application')
    def execute(
        self,
        ticket_id: uuid.UUID,
        *,
        reason: str = '',
    ) -> RefundTicketSchema:
        ticket = self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise NotFoundException(AppErrorCode.RFD_TICKET_NOT_FOUND)
        if ticket.status != 'pending':
            raise ConflictException(AppErrorCode.RFD_NOT_PENDING)

        rejected = self._tickets.mark_rejected(ticket.id, reason=(reason or '')[:500])
        if rejected is None or rejected.status != 'rejected':
            raise ConflictException(AppErrorCode.RFD_NOT_PENDING)
        self._notify(rejected, reason or '')
        return rejected

    def _notify(self, ticket: RefundTicketSchema, reason: str) -> None:
        extra = f' Motivo: {reason}' if reason else ''
        try:
            users = self._recipients.active_user_ids(ticket.schema_name)
            self._notifier.notify(
                RefundNotification(
                    schema_name=ticket.schema_name,
                    ticket_id=ticket.id,
                    ticket_number=ticket.ticket_number,
                    status=ticket.status,
                    title=f'Solicitud {ticket.ticket_number} no aprobada',
                    body=(
                        f'No se aprobó el reembolso a {ticket.to_subscription_name}. '
                        f'Tu plan actual no cambia.{extra}'
                    ),
                    level='WARNING',
                ),
                users,
            )
        except Exception:
            logger.exception('refund rejected notification failed for %s', ticket.ticket_number)
