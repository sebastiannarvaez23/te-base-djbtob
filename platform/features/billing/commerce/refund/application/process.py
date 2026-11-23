"""Move money through the payout port and advance the ticket."""
import logging
import uuid

from core.errors import AppErrorCode, NotFoundException

from ..domain.interfaces import (
    ICompanyRecipientLookup,
    IRefundNotifier,
    IRefundPayoutPort,
    IRefundRequestRepository,
    IRefundableChargeLookup,
)
from ..domain.schemas import RefundNotification, RefundTicketSchema
from core.trace import trace_layer

logger = logging.getLogger('billing.refund')


class ProcessRefundPayoutUseCase:
    def __init__(
        self,
        tickets: IRefundRequestRepository,
        charges: IRefundableChargeLookup,
        payout: IRefundPayoutPort,
        notifier: IRefundNotifier,
        recipients: ICompanyRecipientLookup,
    ):
        self._tickets = tickets
        self._charges = charges
        self._payout = payout
        self._notifier = notifier
        self._recipients = recipients

    @trace_layer('application')
    def execute(self, ticket_id: uuid.UUID | str) -> RefundTicketSchema:
        ticket_id = uuid.UUID(str(ticket_id))
        ticket = self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise NotFoundException(AppErrorCode.RFD_TICKET_NOT_FOUND)
        if ticket.status in ('completed', 'pending', 'rejected'):
            return ticket

        charge = self._charges.get_for_period(ticket.company_id, ticket.period_id)
        already = (
            charge is not None
            and (charge.refunded_amount - ticket.charge_refunded_before) >= ticket.amount
        )
        if already:
            completed = self._tickets.mark_completed(
                ticket.id, gateway_refund_id=ticket.gateway_refund_id or 'already-applied',
            )
            self._notify(completed or ticket, 'completed')
            return completed or ticket

        processing = ticket if ticket.status == 'processing' else self._tickets.mark_processing(ticket.id)
        if processing and processing.status == 'processing' and ticket.status != 'processing':
            self._notify(processing, 'processing')
        current = processing or ticket

        result = self._payout.refund(
            current.charge_id,
            current.amount,
            reason=f'refund {current.ticket_number}',
        )
        if result.ok:
            completed = self._tickets.mark_completed(
                current.id,
                gateway_refund_id=result.gateway_refund_id,
            )
            self._notify(completed or current, 'completed')
            return completed or current

        failed = self._tickets.mark_failed(current.id, error=result.error[:512])
        self._notify(failed or current, 'failed')
        return failed or current

    def _notify(self, ticket: RefundTicketSchema, status: str) -> None:
        titles = {
            'processing': f'Solicitud {ticket.ticket_number} en proceso',
            'completed': f'Reembolso {ticket.ticket_number} acreditado',
            'failed': f'Solicitud {ticket.ticket_number}: no se pudo devolver el dinero',
        }
        bodies = {
            'processing': (
                f'Estamos devolviendo {ticket.amount} {ticket.currency} al medio de pago original. '
                f'El plazo máximo es de 30 días hábiles (hasta {ticket.payout_due_on.isoformat()}).'
            ),
            'completed': (
                f'Se acreditó {ticket.amount} {ticket.currency} del ticket {ticket.ticket_number} '
                f'al medio de pago con el que se cobró el plan.'
            ),
            'failed': (
                f'No pudimos devolver el dinero de {ticket.ticket_number}. '
                f'Reintentaremos. Si el cargo no aparece, contacta a soporte.'
            ),
        }
        level = {'processing': 'INFO', 'completed': 'SUCCESS', 'failed': 'WARNING'}[status]
        try:
            users = self._recipients.active_user_ids(ticket.schema_name)
            self._notifier.notify(
                RefundNotification(
                    schema_name=ticket.schema_name,
                    ticket_id=ticket.id,
                    ticket_number=ticket.ticket_number,
                    status=ticket.status,
                    title=titles[status],
                    body=bodies[status],
                    level=level,
                ),
                users,
            )
        except Exception:
            logger.exception('refund %s notification failed for %s', status, ticket.ticket_number)
