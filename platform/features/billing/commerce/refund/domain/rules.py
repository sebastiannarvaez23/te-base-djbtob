"""Pure refund policy. No I/O — callers inject clocks and snapshots."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional

from core.errors import AppErrorCode, AppException, ConflictException, NotFoundException

WINDOW = timedelta(hours=24)
COOLDOWN = timedelta(days=90)
_TWOPLACES = Decimal('0.01')

RefundKind = Literal['full', 'difference']


def quantize_money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)


def window_closes_at(period_start: datetime) -> datetime:
    return period_start + WINDOW


def window_is_open(period_start: datetime, now: datetime) -> bool:
    return now <= window_closes_at(period_start)


def cooldown_until(last_accepted_at: Optional[datetime]) -> Optional[datetime]:
    if last_accepted_at is None:
        return None
    return last_accepted_at + COOLDOWN


def cooldown_is_active(last_accepted_at: Optional[datetime], now: datetime) -> bool:
    until = cooldown_until(last_accepted_at)
    return until is not None and now < until


def is_free_plan(list_amount: Decimal) -> bool:
    return quantize_money(list_amount) <= 0


def is_relevo(price_paid: Decimal, target_amount: Decimal) -> bool:
    """``price_paid`` is money actually captured, not catalog list price."""
    paid = quantize_money(price_paid)
    target = quantize_money(target_amount)
    if paid <= 0:
        return False
    return target < paid


def refund_amount(price_paid: Decimal, target_amount: Decimal) -> tuple[Decimal, RefundKind]:
    """Return what to send back when switching to ``target_amount``.

    ``price_paid`` must be the captured cobro (charge remaining). Promotions
    discount that cobro — a 20% voucher on a $100 plan captures $80, so a
    full relevo returns $80, not the $100 list price.
    """
    paid = quantize_money(price_paid)
    target = quantize_money(target_amount)
    if not is_relevo(paid, target):
        raise AppException(AppErrorCode.RFD_NOT_RELEVO)
    if is_free_plan(target):
        return paid, 'full'
    return (paid - target), 'difference'


def captured_paid(remaining: Decimal | int | float | str | None) -> Decimal:
    """Money still held from the period cobro (promo-discounted when applicable)."""
    return quantize_money(remaining)


def assert_can_request(
    *,
    period_start: Optional[datetime],
    price_paid: Decimal,
    last_accepted_at: Optional[datetime],
    has_open_ticket: bool,
    now: datetime,
) -> None:
    if has_open_ticket:
        raise ConflictException(AppErrorCode.RFD_OPEN_TICKET)
    if period_start is None:
        raise AppException(AppErrorCode.RFD_NOT_ELIGIBLE)
    if cooldown_is_active(last_accepted_at, now):
        raise AppException(AppErrorCode.RFD_COOLDOWN)
    if not window_is_open(period_start, now):
        raise AppException(AppErrorCode.RFD_WINDOW_CLOSED)
    if quantize_money(price_paid) <= 0:
        raise AppException(AppErrorCode.RFD_NOT_ELIGIBLE)


def assert_target_found(plan) -> None:
    if plan is None:
        raise NotFoundException(AppErrorCode.RFD_TARGET_NOT_FOUND)


def cap_to_charge_remaining(wanted: Decimal, remaining: Decimal) -> Decimal:
    return min(quantize_money(wanted), quantize_money(remaining))
