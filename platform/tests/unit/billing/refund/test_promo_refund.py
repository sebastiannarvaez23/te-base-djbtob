"""Refunds after GIFT / DISCOUNT vouchers use captured cobro, never list price.

Matrix: gift ($0), percent discounts, yearly cycle, partial remaining, ticket
lifecycle (create / approve / payout) and charge-period lookup fallback.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone as tz
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, AppException, ConflictException
from platform.features.billing.commerce.promotion.application.pricing import apply_discount
from platform.features.billing.commerce.refund.application.approve import ApproveRefundUseCase
from platform.features.billing.commerce.refund.application.create import CreateRefundRequestUseCase
from platform.features.billing.commerce.refund.application.evaluate import EvaluateRefundUseCase
from platform.features.billing.commerce.refund.application.process import ProcessRefundPayoutUseCase
from platform.features.billing.commerce.refund.domain.rules import (
    assert_can_request,
    captured_paid,
    is_relevo,
    refund_amount,
)
from platform.features.billing.commerce.refund.domain.schemas import (
    PayoutResult,
    PeriodSnapshot,
    RefundEligibilitySchema,
    RefundPreviewSchema,
    RefundTicketSchema,
    RefundableCharge,
)
from platform.features.billing.commerce.refund.infrastructure.lookups import (
    DjangoRefundableChargeLookup,
    _refundable,
)
from platform.features.billing.subscription.subscription.domain.billing_cycle import charge_amount

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=tz.utc)
_COMPANY = uuid4()
_PLAN = uuid4()
_PERIOD = uuid4()
_CHARGE = uuid4()
_TARGET = uuid4()
_TICKET = uuid4()
_ADMIN = uuid4()


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


def _promo_charge(percent, *, list_amount=Decimal('100.00'), **over):
    captured, _ = apply_discount(list_amount, Decimal(str(percent)))
    return _charge(amount=captured, **over)


def _target(price, name='Starter', is_active=True):
    return SimpleNamespace(id=_TARGET, name=name, price=Decimal(str(price)), is_active=is_active)


def _evaluate(*, period=None, charge=_charge(), open_ticket=None, last=None, target=None):
    tickets = MagicMock()
    tickets.get_open.return_value = open_ticket
    tickets.last_accepted_at.return_value = last
    periods = MagicMock()
    periods.get_active.return_value = period if period is not None else _period()
    charges = MagicMock()
    charges.get_for_period.return_value = charge
    catalog = MagicMock()
    catalog.get_by_id.return_value = target or _target('40.00')
    catalog.get_annual_discount_percent.return_value = Decimal('15')
    return EvaluateRefundUseCase(tickets, periods, charges, catalog)


def _ticket_schema(**over):
    data = dict(
        id=_TICKET, ticket_number='RF-P', company_id=_COMPANY, schema_name='acme',
        from_subscription_id=_PLAN, from_subscription_name='Pro',
        to_subscription_id=_TARGET, to_subscription_name='Free',
        period_id=_PERIOD, charge_id=_CHARGE, amount=Decimal('80.00'),
        currency='USD', kind='full', status='pending',
        payout_due_on=_NOW.date(), charge_refunded_before=Decimal('0'),
        created_at=_NOW,
    )
    data.update(over)
    return RefundTicketSchema(**data)


@contextmanager
def _atomic():
    yield


def _frozen_now():
    return _NOW


def _immediate(fn):
    fn()


# ── Domain rules ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize('captured,target,kind,expected', [
    (Decimal('80.00'), Decimal('0'), 'full', Decimal('80.00')),
    (Decimal('90.00'), Decimal('0'), 'full', Decimal('90.00')),
    (Decimal('50.00'), Decimal('0'), 'full', Decimal('50.00')),
    (Decimal('66.33'), Decimal('0'), 'full', Decimal('66.33')),
    (Decimal('80.00'), Decimal('40.00'), 'difference', Decimal('40.00')),
    (Decimal('80.00'), Decimal('70.00'), 'difference', Decimal('10.00')),
    (Decimal('50.00'), Decimal('40.00'), 'difference', Decimal('10.00')),
    (Decimal('66.33'), Decimal('40.00'), 'difference', Decimal('26.33')),
    (Decimal('40.01'), Decimal('40.00'), 'difference', Decimal('0.01')),
])
def test_discount_refund_uses_captured(captured, target, kind, expected):
    amount, got_kind = refund_amount(captured, target)
    assert got_kind == kind
    assert amount == expected


@pytest.mark.parametrize('captured,target', [
    (Decimal('0'), Decimal('0')),
    (Decimal('0'), Decimal('40')),
    (Decimal('80.00'), Decimal('80.00')),
    (Decimal('80.00'), Decimal('90.00')),
    (Decimal('50.00'), Decimal('70.00')),
    (Decimal('50.00'), Decimal('50.00')),
    (Decimal('816.00'), Decimal('1020.00')),
])
def test_gift_or_non_relevo_rejected(captured, target):
    assert not is_relevo(captured, target)
    with pytest.raises(AppException) as exc:
        refund_amount(captured, target)
    assert exc.value.code == AppErrorCode.RFD_NOT_RELEVO


def test_gift_zero_is_not_relevo_to_free_or_paid():
    assert not is_relevo(Decimal('0'), Decimal('0'))
    assert not is_relevo(Decimal('0'), Decimal('40'))


def test_hundred_percent_discount_same_as_gift():
    captured, _ = apply_discount(Decimal('100'), Decimal('100'))
    assert captured == Decimal('0')
    assert not is_relevo(captured, Decimal('0'))


def test_apply_discount_then_refund_matches_twenty_percent():
    captured, discount = apply_discount(Decimal('100'), Decimal('20'))
    assert captured == Decimal('80.00')
    assert discount == Decimal('20.00')
    amount, kind = refund_amount(captured, Decimal('0'))
    assert kind == 'full'
    assert amount == Decimal('80.00')


def test_captured_paid_quantizes_remaining():
    assert captured_paid(0) == Decimal('0.00')
    assert captured_paid(None) == Decimal('0.00')
    assert captured_paid(Decimal('80')) == Decimal('80.00')
    assert captured_paid(_charge(amount=Decimal('80'), refunded_amount=Decimal('20')).remaining) == Decimal('60.00')


def test_assert_can_request_rejects_gift_zero():
    with pytest.raises(AppException) as exc:
        assert_can_request(
            period_start=_NOW, price_paid=Decimal('0'), last_accepted_at=None,
            has_open_ticket=False, now=_NOW,
        )
    assert exc.value.code == AppErrorCode.RFD_NOT_ELIGIBLE


def test_assert_can_request_accepts_promo_captured():
    assert_can_request(
        period_start=_NOW, price_paid=Decimal('80.00'), last_accepted_at=None,
        has_open_ticket=False, now=_NOW,
    )


# ── Eligibility ──────────────────────────────────────────────────────────────


def test_gift_no_charge_ineligible():
    result = _evaluate(charge=None).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_004'
    assert result.price_paid == Decimal('0.00')


def test_gift_zero_captured_charge_ineligible():
    result = _evaluate(charge=_charge(amount=Decimal('0'))).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_004'
    assert result.price_paid == Decimal('0.00')


def test_hundred_percent_discount_ineligible():
    result = _evaluate(charge=_promo_charge(100)).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_004'
    assert result.price_paid == Decimal('0.00')


@pytest.mark.parametrize('percent,expected_paid', [
    (10, Decimal('90.00')),
    (20, Decimal('80.00')),
    (33, Decimal('67.00')),
    (50, Decimal('50.00')),
])
def test_discount_eligibility_exposes_captured(percent, expected_paid):
    result = _evaluate(
        period=_period(price_paid=Decimal('100.00')),
        charge=_promo_charge(percent),
    ).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is True
    assert result.price_paid == expected_paid


def test_partially_refunded_promo_exposes_remaining():
    result = _evaluate(
        charge=_charge(amount=Decimal('80.00'), refunded_amount=Decimal('20.00')),
    ).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is True
    assert result.price_paid == Decimal('60.00')


def test_promo_still_blocked_after_window():
    result = _evaluate(
        period=_period(start_date=_NOW - timedelta(hours=25)),
        charge=_promo_charge(20),
    ).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_001'
    assert result.price_paid == Decimal('80.00')


def test_promo_still_blocked_during_cooldown():
    result = _evaluate(
        charge=_promo_charge(20),
        last=_NOW - timedelta(days=10),
    ).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_002'


def test_gift_list_price_does_not_override_zero_cobro():
    result = _evaluate(
        period=_period(price_paid=Decimal('100.00')),
        charge=None,
    ).eligibility(_COMPANY, now=_NOW)
    assert result.price_paid != Decimal('100.00')


# ── Preview ──────────────────────────────────────────────────────────────────


def test_gift_preview_is_not_eligible():
    with pytest.raises(AppException) as exc:
        _evaluate(charge=None, target=_target(0, name='Free')).preview(
            _COMPANY, _TARGET, now=_NOW,
        )
    assert exc.value.code == AppErrorCode.RFD_NOT_ELIGIBLE


def test_gift_zero_charge_preview_is_not_eligible():
    with pytest.raises(AppException) as exc:
        _evaluate(charge=_charge(amount=Decimal('0'))).preview(_COMPANY, _TARGET, now=_NOW)
    assert exc.value.code == AppErrorCode.RFD_NOT_ELIGIBLE


@pytest.mark.parametrize('percent,target_price,kind,expected', [
    (20, '0', 'full', Decimal('80.00')),
    (10, '0', 'full', Decimal('90.00')),
    (50, '0', 'full', Decimal('50.00')),
    (20, '40', 'difference', Decimal('40.00')),
    (20, '70', 'difference', Decimal('10.00')),
    (50, '40', 'difference', Decimal('10.00')),
    (10, '40', 'difference', Decimal('50.00')),
])
def test_discount_preview_amounts(percent, target_price, kind, expected):
    name = 'Free' if target_price == '0' else 'Starter'
    preview = _evaluate(
        period=_period(price_paid=Decimal('100.00')),
        charge=_promo_charge(percent),
        target=_target(target_price, name=name),
    ).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == kind
    assert preview.refund_amount == expected
    assert preview.eligibility.price_paid == apply_discount(Decimal('100'), Decimal(str(percent)))[0]


@pytest.mark.parametrize('percent,target_price', [
    (20, '80'),
    (20, '90'),
    (50, '70'),
    (50, '50'),
    (10, '95'),
])
def test_discount_preview_not_relevo_when_target_not_cheaper_than_captured(percent, target_price):
    with pytest.raises(AppException) as exc:
        _evaluate(
            period=_period(price_paid=Decimal('100.00')),
            charge=_promo_charge(percent),
            target=_target(target_price, name='Mid'),
        ).preview(_COMPANY, _TARGET, now=_NOW)
    assert exc.value.code == AppErrorCode.RFD_NOT_RELEVO


def test_discount_upgrade_rejected():
    with pytest.raises(AppException) as exc:
        _evaluate(
            charge=_promo_charge(20),
            target=_target('200', name='Ent'),
        ).preview(_COMPANY, _TARGET, now=_NOW)
    assert exc.value.code == AppErrorCode.RFD_NOT_RELEVO


def test_yearly_discount_full_refunds_captured_cycle():
    list_cycle = charge_amount(Decimal('100'), 'yearly', Decimal('15'))
    captured, _ = apply_discount(list_cycle, Decimal('20'))
    preview = _evaluate(
        period=_period(price_paid=list_cycle, billing_interval='yearly'),
        charge=_charge(amount=captured),
        target=_target(0, name='Free'),
    ).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == 'full'
    assert preview.refund_amount == captured
    assert preview.refund_amount != list_cycle


def test_yearly_discount_difference_uses_captured_cycle():
    list_cycle = charge_amount(Decimal('100'), 'yearly', Decimal('15'))
    captured, _ = apply_discount(list_cycle, Decimal('20'))
    target_cycle = charge_amount(Decimal('40'), 'yearly', Decimal('15'))
    preview = _evaluate(
        period=_period(price_paid=list_cycle, billing_interval='yearly'),
        charge=_charge(amount=captured),
        target=_target('40.00'),
    ).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == 'difference'
    assert preview.refund_amount == captured - target_cycle
    assert preview.target_amount == target_cycle


def test_yearly_gift_not_eligible():
    list_cycle = charge_amount(Decimal('100'), 'yearly', Decimal('15'))
    result = _evaluate(
        period=_period(price_paid=list_cycle, billing_interval='yearly'),
        charge=None,
    ).eligibility(_COMPANY, now=_NOW)
    assert result.eligible is False
    assert result.reason_code == 'RFD_004'


def test_partial_remaining_full_refund():
    preview = _evaluate(
        charge=_charge(amount=Decimal('80.00'), refunded_amount=Decimal('20.00')),
        target=_target(0, name='Free'),
    ).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == 'full'
    assert preview.refund_amount == Decimal('60.00')


def test_partial_remaining_difference():
    preview = _evaluate(
        charge=_charge(amount=Decimal('80.00'), refunded_amount=Decimal('20.00')),
        target=_target('40.00'),
    ).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_kind == 'difference'
    assert preview.refund_amount == Decimal('20.00')


def test_partial_remaining_not_relevo_when_below_target():
    with pytest.raises(AppException) as exc:
        _evaluate(
            charge=_charge(amount=Decimal('80.00'), refunded_amount=Decimal('50.00')),
            target=_target('40.00'),
        ).preview(_COMPANY, _TARGET, now=_NOW)
    assert exc.value.code == AppErrorCode.RFD_NOT_RELEVO


def test_rounding_discount_preview_to_free():
    captured, _ = apply_discount(Decimal('99'), Decimal('33'))
    preview = _evaluate(
        period=_period(price_paid=Decimal('99.00')),
        charge=_charge(amount=captured),
        target=_target(0, name='Free'),
    ).preview(_COMPANY, _TARGET, now=_NOW)
    assert preview.refund_amount == Decimal('66.33')


def test_promo_open_ticket_preview_is_conflict():
    with pytest.raises(ConflictException) as exc:
        _evaluate(
            charge=_promo_charge(20),
            open_ticket=_ticket_schema(status='accepted'),
        ).preview(_COMPANY, _TARGET, now=_NOW)
    assert exc.value.code == AppErrorCode.RFD_OPEN_TICKET


# ── Create ticket ────────────────────────────────────────────────────────────


def _create_uc(*, preview, period, charge):
    evaluate = MagicMock()
    evaluate.preview.return_value = preview
    tickets = MagicMock()
    tickets.get_open.return_value = None
    tickets.last_accepted_at.return_value = None
    tickets.create.return_value = _ticket_schema(amount=preview.refund_amount, kind=preview.refund_kind)
    periods = MagicMock()
    periods.get_active.return_value = period
    charges = MagicMock()
    charges.get_for_period.return_value = charge
    return CreateRefundRequestUseCase(
        evaluate, tickets, periods, charges, MagicMock(), MagicMock(),
    ), tickets


def _preview_schema(*, refund_amount, kind='full', target_amount=Decimal('0')):
    return RefundPreviewSchema(
        eligibility=RefundEligibilitySchema(eligible=True, price_paid=Decimal('80.00')),
        target_plan_id=_TARGET, target_plan_name='Free',
        target_amount=target_amount, refund_amount=refund_amount,
        refund_kind=kind, currency='USD', payout_due_on=_NOW.date(),
    )


@patch('platform.features.billing.commerce.refund.application.create._now', _frozen_now)
@patch('platform.features.billing.commerce.refund.application.create.transaction.atomic', _atomic)
def test_create_stores_promo_captured_not_list():
    preview = _preview_schema(refund_amount=Decimal('80.00'), kind='full')
    uc, tickets = _create_uc(
        preview=preview, period=_period(price_paid=Decimal('100')),
        charge=_promo_charge(20),
    )
    uc.execute(_COMPANY, _TARGET, 'acme')
    schema = tickets.create.call_args.args[0]
    assert schema.amount == Decimal('80.00')
    assert schema.kind == 'full'
    assert schema.amount != Decimal('100')


@patch('platform.features.billing.commerce.refund.application.create._now', _frozen_now)
@patch('platform.features.billing.commerce.refund.application.create.transaction.atomic', _atomic)
def test_create_stores_promo_difference():
    preview = _preview_schema(
        refund_amount=Decimal('40.00'), kind='difference', target_amount=Decimal('40.00'),
    )
    uc, tickets = _create_uc(
        preview=preview, period=_period(), charge=_promo_charge(20),
    )
    uc.execute(_COMPANY, _TARGET, 'acme')
    schema = tickets.create.call_args.args[0]
    assert schema.amount == Decimal('40.00')
    assert schema.kind == 'difference'


@patch('platform.features.billing.commerce.refund.application.create._now', _frozen_now)
@patch('platform.features.billing.commerce.refund.application.create.transaction.atomic', _atomic)
def test_create_gift_remaining_zero_rejected():
    preview = _preview_schema(refund_amount=Decimal('100.00'), kind='full')
    uc, tickets = _create_uc(
        preview=preview, period=_period(price_paid=Decimal('100')),
        charge=_charge(amount=Decimal('0')),
    )
    with pytest.raises(AppException) as exc:
        uc.execute(_COMPANY, _TARGET, 'acme')
    assert exc.value.code == AppErrorCode.RFD_NOT_ELIGIBLE
    tickets.create.assert_not_called()


@patch('platform.features.billing.commerce.refund.application.create._now', _frozen_now)
@patch('platform.features.billing.commerce.refund.application.create.transaction.atomic', _atomic)
def test_create_gift_missing_charge_rejected():
    preview = _preview_schema(refund_amount=Decimal('100.00'), kind='full')
    uc, tickets = _create_uc(
        preview=preview, period=_period(price_paid=Decimal('100')), charge=None,
    )
    with pytest.raises(AppException) as exc:
        uc.execute(_COMPANY, _TARGET, 'acme')
    assert exc.value.code == AppErrorCode.RFD_NOT_ELIGIBLE
    tickets.create.assert_not_called()


# ── Approve / payout ─────────────────────────────────────────────────────────


@patch('platform.features.billing.commerce.refund.application.approve.transaction.atomic', _atomic)
@patch('platform.features.billing.commerce.refund.application.approve.transaction.on_commit', _immediate)
def test_approve_promo_ticket_uses_captured_remaining():
    tickets = MagicMock()
    tickets.get_by_id.return_value = _ticket_schema(amount=Decimal('80.00'), status='pending')
    tickets.mark_approved.return_value = _ticket_schema(amount=Decimal('80.00'), status='accepted')
    periods = MagicMock()
    periods.get_active.return_value = _period()
    charges = MagicMock()
    charges.get_for_period.return_value = _promo_charge(20)
    company_periods = MagicMock()
    company_periods.activate_plan.return_value = MagicMock()
    enqueue = MagicMock()

    result = ApproveRefundUseCase(
        tickets, periods, charges, company_periods,
        MagicMock(), MagicMock(), enqueue, MagicMock(),
    ).execute(_TICKET, approved_by_id=_ADMIN)

    assert result.status == 'accepted'
    enqueue.assert_called_once_with(_TICKET)


@patch('platform.features.billing.commerce.refund.application.approve.transaction.atomic', _atomic)
def test_approve_gift_without_remaining_rejected():
    tickets = MagicMock()
    tickets.get_by_id.return_value = _ticket_schema(status='pending')
    charges = MagicMock()
    charges.get_for_period.return_value = None
    uc = ApproveRefundUseCase(
        tickets, MagicMock(), charges, MagicMock(),
        MagicMock(), MagicMock(), MagicMock(), MagicMock(),
    )
    with pytest.raises(AppException) as exc:
        uc.execute(_TICKET)
    assert exc.value.code == AppErrorCode.RFD_NOT_ELIGIBLE
    tickets.mark_approved.assert_not_called()


def test_payout_refunds_promo_captured_amount():
    ticket = _ticket_schema(amount=Decimal('80.00'), kind='full', status='accepted')
    tickets = MagicMock()
    tickets.get_by_id.return_value = ticket
    tickets.mark_processing.return_value = _ticket_schema(amount=Decimal('80.00'), status='processing')
    tickets.mark_completed.return_value = _ticket_schema(amount=Decimal('80.00'), status='completed')
    charges = MagicMock()
    charges.get_for_period.return_value = _promo_charge(20)
    payout = MagicMock()
    payout.refund.return_value = PayoutResult(
        ok=True, refunded_amount=Decimal('80.00'), gateway_refund_id='sim_rf_promo',
    )
    recipients = MagicMock()
    recipients.active_user_ids.return_value = [uuid4()]

    result = ProcessRefundPayoutUseCase(
        tickets, charges, payout, MagicMock(), recipients,
    ).execute(_TICKET)

    payout.refund.assert_called_once()
    assert payout.refund.call_args.args[0] == _CHARGE
    assert payout.refund.call_args.args[1] == Decimal('80.00')
    assert result.status == 'completed'


def test_payout_refunds_promo_difference_amount():
    ticket = _ticket_schema(amount=Decimal('40.00'), kind='difference', status='accepted')
    tickets = MagicMock()
    tickets.get_by_id.return_value = ticket
    tickets.mark_processing.return_value = _ticket_schema(
        amount=Decimal('40.00'), kind='difference', status='processing',
    )
    tickets.mark_completed.return_value = _ticket_schema(
        amount=Decimal('40.00'), kind='difference', status='completed',
    )
    charges = MagicMock()
    charges.get_for_period.return_value = _promo_charge(20)
    payout = MagicMock()
    payout.refund.return_value = PayoutResult(
        ok=True, refunded_amount=Decimal('40.00'), gateway_refund_id='sim_rf_diff',
    )
    recipients = MagicMock()
    recipients.active_user_ids.return_value = [uuid4()]

    ProcessRefundPayoutUseCase(
        tickets, charges, payout, MagicMock(), recipients,
    ).execute(_TICKET)

    assert payout.refund.call_args.args[1] == Decimal('40.00')


# ── Charge lookup (promo onboarding bind gap) ────────────────────────────────


def _row(amount, refunded=Decimal('0')):
    return {
        'id': uuid4(),
        'amount': Decimal(str(amount)),
        'refunded_amount': Decimal(str(refunded)),
        'currency': 'USD',
        'status': 'captured',
    }


def test_refundable_none():
    assert _refundable(None) is None


def test_refundable_gift_zero_dropped():
    assert _refundable(_row('0')) is None


def test_refundable_fully_refunded_dropped():
    assert _refundable(_row('80', refunded=Decimal('80'))) is None


def test_refundable_promo_kept():
    charge = _refundable(_row('80'))
    assert charge is not None
    assert charge.amount == Decimal('80')
    assert charge.remaining == Decimal('80')


class _ChargeQuery:
    def __init__(self, *, bound=None, unbound=None, scope='base'):
        self.bound = bound
        self.unbound = unbound
        self.scope = scope

    def filter(self, **kwargs):
        if kwargs.get('company_subscription_id__isnull') is True:
            return _ChargeQuery(bound=self.bound, unbound=self.unbound, scope='unbound')
        if 'company_subscription_id' in kwargs:
            return _ChargeQuery(bound=self.bound, unbound=self.unbound, scope='period')
        return self

    def order_by(self, *args):
        return self

    def values(self, *args):
        return self

    def first(self):
        if self.scope == 'period':
            return self.bound
        if self.scope == 'unbound':
            return self.unbound
        return None


@patch('platform.features.billing.commerce.refund.infrastructure.lookups.Charge')
def test_lookup_prefers_charge_bound_to_period(MockCharge):
    bound = _row('80')
    MockCharge.objects.filter.return_value = _ChargeQuery(
        bound=bound, unbound=_row('50'),
    )
    found = DjangoRefundableChargeLookup().get_for_period(_COMPANY, _PERIOD)
    assert found is not None
    assert found.id == bound['id']
    assert found.amount == Decimal('80')


@patch('platform.features.billing.commerce.refund.infrastructure.lookups.Charge')
def test_lookup_does_not_fallback_when_bound_charge_is_spent(MockCharge):
    MockCharge.objects.filter.return_value = _ChargeQuery(
        bound=_row('80', refunded=Decimal('80')),
        unbound=_row('80'),
    )
    assert DjangoRefundableChargeLookup().get_for_period(_COMPANY, _PERIOD) is None


@patch('platform.features.billing.commerce.refund.infrastructure.lookups.Charge')
def test_lookup_falls_back_only_to_unbound_promo_charge(MockCharge):
    unbound = _row('80')
    MockCharge.objects.filter.return_value = _ChargeQuery(bound=None, unbound=unbound)
    found = DjangoRefundableChargeLookup().get_for_period(_COMPANY, _PERIOD)
    assert found is not None
    assert found.amount == Decimal('80.00')


@patch('platform.features.billing.commerce.refund.infrastructure.lookups.Charge')
def test_lookup_does_not_pick_another_period_charge(MockCharge):
    MockCharge.objects.filter.return_value = _ChargeQuery(bound=None, unbound=None)
    assert DjangoRefundableChargeLookup().get_for_period(_COMPANY, _PERIOD) is None


@patch('platform.features.billing.commerce.refund.infrastructure.lookups.Charge')
def test_lookup_fallback_ignores_gift_zero_charge(MockCharge):
    MockCharge.objects.filter.return_value = _ChargeQuery(bound=None, unbound=_row('0'))
    assert DjangoRefundableChargeLookup().get_for_period(_COMPANY, _PERIOD) is None
