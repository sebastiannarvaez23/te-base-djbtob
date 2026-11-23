import uuid
from datetime import datetime, timedelta, timezone as tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, AppException, ConflictException
from platform.features.billing.commerce.refund.application.evaluate import EvaluateRefundUseCase
from platform.features.billing.commerce.refund.domain.schemas import (
    PeriodSnapshot,
    RefundTicketSchema,
    RefundableCharge,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=tz.utc)
_COMPANY = uuid.uuid4()
_PLAN = uuid.uuid4()
_PERIOD = uuid.uuid4()
_CHARGE = uuid.uuid4()
_TARGET = uuid.uuid4()


def _period(**over):
    data = dict(
        id=_PERIOD, company_id=_COMPANY, subscription_id=_PLAN,
        subscription_name='Pro', start_date=_NOW - timedelta(hours=2),
        price_paid=Decimal('100.00'), billing_interval='monthly', status='active',
    )
    data.update(over)
    return PeriodSnapshot(**data)


def _charge(**over):
    data = dict(
        id=_CHARGE, amount=Decimal('100.00'), refunded_amount=Decimal('0'),
        currency='USD', status='captured',
    )
    data.update(over)
    return RefundableCharge(**data)


def _ticket():
    return RefundTicketSchema(
        id=uuid.uuid4(), ticket_number='RF-1', company_id=_COMPANY,
        schema_name='acme', from_subscription_id=_PLAN, from_subscription_name='Pro',
        to_subscription_id=_TARGET, to_subscription_name='Free',
        period_id=_PERIOD, charge_id=_CHARGE, amount=Decimal('100'),
        currency='USD', kind='full', status='accepted',
        payout_due_on=_NOW.date(), charge_refunded_before=Decimal('0'),
        created_at=_NOW,
    )


def _uc(period=_period(), charge=_charge(), open_ticket=None, last=None, target=None):
    tickets = MagicMock()
    tickets.get_open.return_value = open_ticket
    tickets.last_accepted_at.return_value = last
    periods = MagicMock()
    periods.get_active.return_value = period
    charges = MagicMock()
    charges.get_for_period.return_value = charge
    catalog = MagicMock()
    catalog.get_by_id.return_value = target or SimpleNamespace(
        id=_TARGET, name='Starter', price=Decimal('40.00'), is_active=True,
    )
    catalog.get_annual_discount_percent.return_value = Decimal('15')
    return EvaluateRefundUseCase(tickets, periods, charges, catalog)


def test_eligible_inside_window():
    result = _uc().eligibility(_COMPANY, now=_NOW)
    assert result.eligible is True
    assert result.reason_code is None
    assert result.price_paid == Decimal('100.00')


def test_ineligible_after_window():
    result = _uc(period=_period(start_date=_NOW - timedelta(hours=25))).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_001'


def test_ineligible_during_cooldown():
    result = _uc(last=_NOW - timedelta(days=10)).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_002'


def test_ineligible_open_ticket():
    result = _uc(open_ticket=_ticket()).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_005'


def test_preview_difference():
    preview = _uc().preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == 'difference'
    assert preview.refund_amount == Decimal('60.00')
    assert preview.switches_immediately is False


def test_preview_full_to_free():
    catalog_target = SimpleNamespace(
        id=_TARGET, name='Free', price=Decimal('0'), is_active=True,
    )
    preview = _uc(target=catalog_target).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == 'full'
    assert preview.refund_amount == Decimal('100.00')


def test_preview_upgrade_rejected():
    expensive = SimpleNamespace(
        id=_TARGET, name='Ent', price=Decimal('200'), is_active=True,
    )
    with pytest.raises(AppException) as exc:
        _uc(target=expensive).preview(_COMPANY, _TARGET, now=_NOW)
    assert exc.value.code == AppErrorCode.RFD_NOT_RELEVO


def test_preview_blocked_by_window():
    with pytest.raises(AppException) as exc:
        _uc(period=_period(start_date=_NOW - timedelta(days=3))).preview(
            _COMPANY, _TARGET, now=_NOW,
        )
    assert exc.value.code == AppErrorCode.RFD_WINDOW_CLOSED


def test_preview_open_ticket_is_conflict():
    with pytest.raises(ConflictException) as exc:
        _uc(open_ticket=_ticket()).preview(_COMPANY, _TARGET, now=_NOW)
    assert exc.value.code == AppErrorCode.RFD_OPEN_TICKET


def test_eligibility_exposes_captured_amount_not_list_price():
    result = _uc(
        period=_period(price_paid=Decimal('100.00')),
        charge=_charge(amount=Decimal('80.00')),
    ).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is True
    assert result.price_paid == Decimal('80.00')


def test_gift_charge_not_eligible_despite_list_price():
    result = _uc(
        period=_period(price_paid=Decimal('100.00')),
        charge=None,
    ).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_004'
    assert result.price_paid == Decimal('0.00')


def test_preview_promo_full_refunds_captured_only():
    catalog_target = SimpleNamespace(
        id=_TARGET, name='Free', price=Decimal('0'), is_active=True,
    )
    preview = _uc(
        period=_period(price_paid=Decimal('100.00')),
        charge=_charge(amount=Decimal('80.00')),
        target=catalog_target,
    ).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == 'full'
    assert preview.refund_amount == Decimal('80.00')


def test_preview_promo_difference_uses_captured():
    preview = _uc(
        period=_period(price_paid=Decimal('100.00')),
        charge=_charge(amount=Decimal('80.00')),
    ).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == 'difference'
    assert preview.refund_amount == Decimal('40.00')


def test_preview_promo_not_relevo_when_captured_below_target():
    mid = SimpleNamespace(
        id=_TARGET, name='Mid', price=Decimal('70.00'), is_active=True,
    )
    with pytest.raises(AppException) as exc:
        _uc(
            period=_period(price_paid=Decimal('100.00')),
            charge=_charge(amount=Decimal('50.00')),
            target=mid,
        ).preview(_COMPANY, _TARGET, now=_NOW)
    assert exc.value.code == AppErrorCode.RFD_NOT_RELEVO
