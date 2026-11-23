from datetime import datetime, timedelta, timezone as tz
from decimal import Decimal

import pytest

from core.errors import AppErrorCode, AppException, ConflictException, NotFoundException
from platform.features.billing.commerce.refund.domain.rules import (
    assert_can_request,
    assert_target_found,
    cap_to_charge_remaining,
    cooldown_is_active,
    is_relevo,
    refund_amount,
    window_is_open,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=tz.utc)


def test_window_open_inside_24h():
    assert window_is_open(_NOW - timedelta(hours=23, minutes=59), _NOW)


def test_window_closed_after_24h():
    assert not window_is_open(_NOW - timedelta(hours=24, seconds=1), _NOW)


def test_cooldown_three_months():
    assert cooldown_is_active(_NOW - timedelta(days=89), _NOW)
    assert not cooldown_is_active(_NOW - timedelta(days=90), _NOW)
    assert not cooldown_is_active(None, _NOW)


def test_full_refund_to_free():
    amount, kind = refund_amount(Decimal('99.99'), Decimal('0'))
    assert amount == Decimal('99.99')
    assert kind == 'full'


def test_difference_refund():
    amount, kind = refund_amount(Decimal('100.00'), Decimal('40.00'))
    assert amount == Decimal('60.00')
    assert kind == 'difference'


def test_same_or_higher_is_not_relevo():
    assert not is_relevo(Decimal('50'), Decimal('50'))
    assert not is_relevo(Decimal('50'), Decimal('80'))
    with pytest.raises(AppException) as exc:
        refund_amount(Decimal('50'), Decimal('80'))
    assert exc.value.code == AppErrorCode.RFD_NOT_RELEVO


def test_gift_period_not_relevo():
    assert not is_relevo(Decimal('0'), Decimal('0'))


def test_assert_can_request_open_ticket():
    with pytest.raises(ConflictException) as exc:
        assert_can_request(
            period_start=_NOW, price_paid=Decimal('10'), last_accepted_at=None,
            has_open_ticket=True, now=_NOW,
        )
    assert exc.value.code == AppErrorCode.RFD_OPEN_TICKET


def test_assert_can_request_window():
    with pytest.raises(AppException) as exc:
        assert_can_request(
            period_start=_NOW - timedelta(days=2), price_paid=Decimal('10'),
            last_accepted_at=None, has_open_ticket=False, now=_NOW,
        )
    assert exc.value.code == AppErrorCode.RFD_WINDOW_CLOSED


def test_assert_target_missing():
    with pytest.raises(NotFoundException) as exc:
        assert_target_found(None)
    assert exc.value.code == AppErrorCode.RFD_TARGET_NOT_FOUND


def test_cap_to_remaining():
    assert cap_to_charge_remaining(Decimal('80'), Decimal('30')) == Decimal('30.00')


def test_promo_full_refund_returns_captured_not_list():
    amount, kind = refund_amount(Decimal('80.00'), Decimal('0'))
    assert amount == Decimal('80.00')
    assert kind == 'full'


def test_promo_difference_uses_captured():
    amount, kind = refund_amount(Decimal('80.00'), Decimal('40.00'))
    assert amount == Decimal('40.00')
    assert kind == 'difference'


def test_promo_captured_below_target_is_not_relevo():
    assert not is_relevo(Decimal('50.00'), Decimal('70.00'))
    with pytest.raises(AppException) as exc:
        refund_amount(Decimal('50.00'), Decimal('70.00'))
    assert exc.value.code == AppErrorCode.RFD_NOT_RELEVO
