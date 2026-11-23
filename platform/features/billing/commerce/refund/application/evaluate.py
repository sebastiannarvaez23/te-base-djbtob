"""Evaluate refund eligibility and a preview of the money/plan switch."""
from datetime import datetime, timezone as tz
from typing import Optional
from uuid import UUID

from core.errors import AppErrorCode, AppException, ConflictException, NotFoundException

from platform.features.billing.subscription.subscription.domain.billing_cycle import charge_amount
from platform.features.billing.subscription.subscription.domain.interfaces import IPlanCatalogRepository

from ..domain.calendar import SLA_BUSINESS_DAYS, add_business_days
from ..domain.interfaces import (
    IPeriodSnapshotLookup,
    IRefundRequestRepository,
    IRefundableChargeLookup,
)
from ..domain.rules import (
    COOLDOWN,
    cap_to_charge_remaining,
    captured_paid,
    cooldown_until,
    is_relevo,
    refund_amount,
    window_closes_at,
    window_is_open,
)
from ..domain.schemas import (
    PeriodSnapshot,
    RefundEligibilitySchema,
    RefundPreviewSchema,
    RefundTicketSchema,
    RefundableCharge,
)
from core.trace import trace_layer

_REASON_TO_CODE = {
    'RFD_001': AppErrorCode.RFD_WINDOW_CLOSED,
    'RFD_002': AppErrorCode.RFD_COOLDOWN,
    'RFD_004': AppErrorCode.RFD_NOT_ELIGIBLE,
    'RFD_005': AppErrorCode.RFD_OPEN_TICKET,
}


def _now() -> datetime:
    return datetime.now(tz.utc)


class EvaluateRefundUseCase:
    def __init__(
        self,
        tickets: IRefundRequestRepository,
        periods: IPeriodSnapshotLookup,
        charges: IRefundableChargeLookup,
        catalog: IPlanCatalogRepository,
    ):
        self._tickets = tickets
        self._periods = periods
        self._charges = charges
        self._catalog = catalog

    @trace_layer('application')
    def eligibility(self, company_id: UUID, *, now: Optional[datetime] = None) -> RefundEligibilitySchema:
        clock = now or _now()
        period, charge, open_ticket, last_accepted = self._load(company_id)
        return self._eligibility(period, charge, open_ticket, last_accepted, clock)

    @trace_layer('application')
    def preview(
        self,
        company_id: UUID,
        target_subscription_id: UUID,
        *,
        now: Optional[datetime] = None,
    ) -> RefundPreviewSchema:
        clock = now or _now()
        period, charge, open_ticket, last_accepted = self._load(company_id)
        eligibility = self._eligibility(period, charge, open_ticket, last_accepted, clock)
        if not eligibility.eligible:
            code = _REASON_TO_CODE.get(eligibility.reason_code or '', AppErrorCode.RFD_NOT_ELIGIBLE)
            if code is AppErrorCode.RFD_OPEN_TICKET:
                raise ConflictException(code)
            raise AppException(code)
        target = self._catalog.get_by_id(target_subscription_id)
        if target is None or not target.is_active:
            raise NotFoundException(AppErrorCode.RFD_TARGET_NOT_FOUND)
        if period is None:
            raise AppException(AppErrorCode.RFD_NOT_ELIGIBLE)
        paid = captured_paid(charge.remaining if charge else 0)
        if paid <= 0:
            raise AppException(AppErrorCode.RFD_NOT_ELIGIBLE)
        annual = self._catalog.get_annual_discount_percent()
        target_amount = charge_amount(target.price, period.billing_interval, annual)
        if not is_relevo(paid, target_amount):
            raise AppException(AppErrorCode.RFD_NOT_RELEVO)
        amount, kind = refund_amount(paid, target_amount)
        amount = cap_to_charge_remaining(amount, paid)
        assert charge is not None
        return RefundPreviewSchema(
            eligibility=eligibility,
            target_plan_id=target.id,
            target_plan_name=target.name,
            target_amount=target_amount,
            refund_amount=amount,
            refund_kind=kind,
            currency=charge.currency,
            payout_due_on=add_business_days(clock.date()),
            cooldown_after_days=int(COOLDOWN.days),
        )

    def _load(
        self, company_id: UUID,
    ) -> tuple[
        Optional[PeriodSnapshot],
        Optional[RefundableCharge],
        Optional[RefundTicketSchema],
        Optional[datetime],
    ]:
        period = self._periods.get_active(company_id)
        charge = self._charges.get_for_period(company_id, period.id) if period else None
        return (
            period,
            charge,
            self._tickets.get_open(company_id),
            self._tickets.last_accepted_at(company_id),
        )

    def _eligibility(
        self,
        period: Optional[PeriodSnapshot],
        charge: Optional[RefundableCharge],
        open_ticket: Optional[RefundTicketSchema],
        last_accepted: Optional[datetime],
        clock: datetime,
    ) -> RefundEligibilitySchema:
        until = cooldown_until(last_accepted)
        if period is None:
            return RefundEligibilitySchema(
                eligible=False,
                reason_code='RFD_004',
                cooldown_until=until if until and clock < until else None,
                sla_business_days=SLA_BUSINESS_DAYS,
                cooldown_days=int(COOLDOWN.days),
                open_ticket=open_ticket,
            )
        paid = captured_paid(charge.remaining if charge else 0)
        reason = None
        eligible = True
        if open_ticket is not None:
            eligible, reason = False, 'RFD_005'
        elif until is not None and clock < until:
            eligible, reason = False, 'RFD_002'
        elif not window_is_open(period.start_date, clock):
            eligible, reason = False, 'RFD_001'
        elif paid <= 0:
            eligible, reason = False, 'RFD_004'
        return RefundEligibilitySchema(
            eligible=eligible,
            reason_code=reason,
            window_ends_at=window_closes_at(period.start_date),
            cooldown_until=until if until and clock < until else None,
            current_plan_id=period.subscription_id,
            current_plan_name=period.subscription_name,
            price_paid=paid,
            billing_interval=period.billing_interval,
            sla_business_days=SLA_BUSINESS_DAYS,
            cooldown_days=int(COOLDOWN.days),
            open_ticket=open_ticket,
        )
