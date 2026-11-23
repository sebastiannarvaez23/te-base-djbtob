"""Admin approval: switch plan now and enqueue the payout."""
import logging
import uuid
from typing import Callable, Optional

from django.db import transaction

from core.errors import AppErrorCode, AppException, ConflictException, NotFoundException

from platform.features.billing.subscription.subscription.domain.interfaces import ICompanyPeriodRepository

from ..domain.calendar import add_business_days
from ..domain.interfaces import (
    ICompanyRecipientLookup,
    IPeriodSnapshotLookup,
    IRefundNotifier,
    IRefundRequestRepository,
    IRefundableChargeLookup,
)
from ..domain.rules import cap_to_charge_remaining
from ..domain.schemas import RefundNotification, RefundTicketSchema
from .evaluate import _now
from core.trace import trace_layer

logger = logging.getLogger('billing.refund')

EnqueueFn = Callable[[uuid.UUID], None]
KillCompanySessionsFn = Callable[[uuid.UUID], int]


class ApproveRefundUseCase:
    def __init__(
        self,
        tickets: IRefundRequestRepository,
        periods: IPeriodSnapshotLookup,
        charges: IRefundableChargeLookup,
        company_periods: ICompanyPeriodRepository,
        notifier: IRefundNotifier,
        recipients: ICompanyRecipientLookup,
        enqueue: EnqueueFn,
        kill_company_sessions: KillCompanySessionsFn,
    ):
        self._tickets = tickets
        self._periods = periods
        self._charges = charges
        self._company_periods = company_periods
        self._notifier = notifier
        self._recipients = recipients
        self._enqueue = enqueue
        self._kill_company_sessions = kill_company_sessions

    @trace_layer('application')
    def execute(
        self,
        ticket_id: uuid.UUID,
        *,
        approved_by_id: Optional[uuid.UUID] = None,
    ) -> RefundTicketSchema:
        ticket = self._tickets.get_by_id(ticket_id)
        if ticket is None:
            raise NotFoundException(AppErrorCode.RFD_TICKET_NOT_FOUND)
        if ticket.status != 'pending':
            raise ConflictException(AppErrorCode.RFD_NOT_PENDING)

        charge = self._charges.get_for_period(ticket.company_id, ticket.period_id)
        if charge is None:
            raise AppException(AppErrorCode.RFD_NOT_ELIGIBLE)
        amount = cap_to_charge_remaining(ticket.amount, charge.remaining)
        if amount <= 0:
            raise AppException(AppErrorCode.RFD_NOT_ELIGIBLE)

        due = add_business_days(_now().date())
        with transaction.atomic():
            approved = self._tickets.mark_approved(
                ticket.id, approved_by_id=approved_by_id, payout_due_on=due,
            )
            if approved is None or approved.status != 'accepted':
                raise ConflictException(AppErrorCode.RFD_NOT_PENDING)

            period = self._periods.get_active(ticket.company_id)
            interval = period.billing_interval if period else 'monthly'
            switched = self._company_periods.activate_plan(
                ticket.company_id,
                ticket.to_subscription_id,
                billing_interval=interval,
            )
            if switched is None:
                raise AppException(AppErrorCode.RFD_TARGET_NOT_FOUND)

            ticket_id = approved.id
            transaction.on_commit(lambda: self._enqueue(ticket_id))

        self._kill_sessions(ticket.company_id)
        self._notify(approved)
        return approved

    def _kill_sessions(self, company_id: uuid.UUID) -> None:
        try:
            self._kill_company_sessions(company_id)
        except Exception:
            logger.exception(
                'refund approved: failed to kill sessions for company=%s', company_id,
            )

    def _notify(self, ticket: RefundTicketSchema) -> None:
        try:
            users = self._recipients.active_user_ids(ticket.schema_name)
            self._notifier.notify(
                RefundNotification(
                    schema_name=ticket.schema_name,
                    ticket_id=ticket.id,
                    ticket_number=ticket.ticket_number,
                    status=ticket.status,
                    title=f'Solicitud {ticket.ticket_number} aprobada',
                    body=(
                        f'Ya estás en {ticket.to_subscription_name}. '
                        f'Devolveremos {ticket.amount} {ticket.currency} al medio de pago original '
                        f'en un máximo de 30 días hábiles (hasta {ticket.payout_due_on.isoformat()}). '
                        f'Durante 3 meses no podrás pedir otro reembolso.'
                    ),
                    level='SUCCESS',
                ),
                users,
            )
        except Exception:
            logger.exception('refund approved notification failed for %s', ticket.ticket_number)
