"""Open a refund ticket. Plan switch and payout wait for admin approval."""
import logging
import uuid
from typing import Optional

from django.db import IntegrityError, transaction

from core.errors import AppErrorCode, AppException, ConflictException, ValidationAppException

from ..domain.interfaces import (
    ICompanyRecipientLookup,
    IPeriodSnapshotLookup,
    IRefundNotifier,
    IRefundRequestRepository,
    IRefundableChargeLookup,
)
from ..domain.rules import assert_can_request, cap_to_charge_remaining, captured_paid
from ..domain.schemas import CreateRefundTicketSchema, RefundNotification, RefundTicketSchema
from .evaluate import EvaluateRefundUseCase, _now
from core.trace import trace_layer

logger = logging.getLogger('billing.refund')


def _ticket_number() -> str:
    return f"RF-{_now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class CreateRefundRequestUseCase:
    def __init__(
        self,
        evaluate: EvaluateRefundUseCase,
        tickets: IRefundRequestRepository,
        periods: IPeriodSnapshotLookup,
        charges: IRefundableChargeLookup,
        notifier: IRefundNotifier,
        recipients: ICompanyRecipientLookup,
    ):
        self._evaluate = evaluate
        self._tickets = tickets
        self._periods = periods
        self._charges = charges
        self._notifier = notifier
        self._recipients = recipients

    @trace_layer('application')
    def execute(
        self,
        company_id: uuid.UUID,
        target_subscription_id: uuid.UUID,
        schema_name: str,
        requested_by_id: Optional[uuid.UUID] = None,
    ) -> RefundTicketSchema:
        preview = self._evaluate.preview(company_id, target_subscription_id)
        period = self._periods.get_active(company_id)
        charge = self._charges.get_for_period(company_id, period.id) if period else None
        last_accepted = self._tickets.last_accepted_at(company_id)
        assert_can_request(
            period_start=period.start_date if period else None,
            price_paid=captured_paid(charge.remaining if charge else 0),
            last_accepted_at=last_accepted,
            has_open_ticket=self._tickets.get_open(company_id) is not None,
            now=_now(),
        )
        if charge is None:
            raise AppException(AppErrorCode.RFD_NOT_ELIGIBLE)
        charge_currency = (charge.currency or '').strip().upper()
        preview_currency = (preview.currency or '').strip().upper()
        if not charge_currency or preview_currency != charge_currency:
            raise ValidationAppException(AppErrorCode.PAY_CURRENCY_MISMATCH)
        amount = cap_to_charge_remaining(preview.refund_amount, charge.remaining)
        if amount <= 0:
            raise AppException(AppErrorCode.RFD_NOT_ELIGIBLE)

        with transaction.atomic():
            try:
                ticket = self._tickets.create(CreateRefundTicketSchema(
                    company_id=company_id,
                    schema_name=schema_name,
                    ticket_number=_ticket_number(),
                    from_subscription_id=period.subscription_id,
                    from_subscription_name=period.subscription_name,
                    to_subscription_id=preview.target_plan_id,
                    to_subscription_name=preview.target_plan_name,
                    period_id=period.id,
                    charge_id=charge.id,
                    amount=amount,
                    currency=charge_currency,
                    kind=preview.refund_kind,
                    payout_due_on=preview.payout_due_on,
                    charge_refunded_before=charge.refunded_amount,
                    requested_by_id=requested_by_id,
                ))
            except IntegrityError:
                logger.exception('refund ticket persist failed')
                raise ConflictException(AppErrorCode.RFD_OPEN_TICKET)

        self._notify_submitted(ticket)
        return ticket

    def _notify_submitted(self, ticket: RefundTicketSchema) -> None:
        try:
            users = self._recipients.active_user_ids(ticket.schema_name)
            self._notifier.notify(
                RefundNotification(
                    schema_name=ticket.schema_name,
                    ticket_id=ticket.id,
                    ticket_number=ticket.ticket_number,
                    status=ticket.status,
                    title=f'Solicitud {ticket.ticket_number} recibida',
                    body=(
                        f'Tu reembolso a {ticket.to_subscription_name} quedó en revisión. '
                        f'Se devolverán {ticket.amount} {ticket.currency} al medio original '
                        f'solo si un administrador la aprueba. Te avisaremos en la campanita.'
                    ),
                    level='INFO',
                ),
                users,
            )
        except Exception:
            logger.exception('refund submitted notification failed for %s', ticket.ticket_number)
