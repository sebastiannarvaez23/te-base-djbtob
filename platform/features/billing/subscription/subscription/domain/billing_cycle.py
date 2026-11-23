"""Billing cycle math for subscription charges and vigencia.

Plans store a single monthly list price. A company may pay monthly or
yearly. Yearly is twelve monthly periods minus a configurable discount
(default 15%), parameterized from admin:

    yearly = (monthly × 12) × (1 − percent / 100)
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MONTHLY = 'monthly'
YEARLY = 'yearly'
BILLING_INTERVALS = (MONTHLY, YEARLY)

DEFAULT_ANNUAL_DISCOUNT_PERCENT = Decimal('15')
# Alias kept so existing imports/tests keep working without a DB.
ANNUAL_DISCOUNT_PERCENT = DEFAULT_ANNUAL_DISCOUNT_PERCENT
ANNUAL_MONTHS = 12
MONTHLY_PERIOD_DAYS = 30
YEARLY_PERIOD_DAYS = 365

_TWOPLACES = Decimal('0.01')


def normalize_billing_interval(value) -> str:
    """Return a known interval. Blank/None defaults to monthly."""
    if value in (None, ''):
        return MONTHLY
    interval = str(value).strip().lower()
    if interval not in BILLING_INTERVALS:
        raise ValueError(f'Invalid billing interval: {value!r}')
    return interval


def coerce_annual_discount_percent(value) -> Decimal:
    """Return a 0–100 percent, or the platform default if the value is unusable."""
    if value is None:
        return DEFAULT_ANNUAL_DISCOUNT_PERCENT
    try:
        percent = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return DEFAULT_ANNUAL_DISCOUNT_PERCENT
    if percent < 0 or percent > 100:
        return DEFAULT_ANNUAL_DISCOUNT_PERCENT
    return percent.quantize(_TWOPLACES, rounding=ROUND_HALF_UP)


def yearly_amount(monthly_price: Decimal, discount_percent=None) -> Decimal:
    """Twelve months of ``monthly_price`` minus the annual discount."""
    percent = coerce_annual_discount_percent(discount_percent)
    gross = Decimal(str(monthly_price or 0)) * Decimal(ANNUAL_MONTHS)
    discount = (
        gross * percent / Decimal('100')
    ).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    return (gross - discount).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)


def charge_amount(
    monthly_price: Decimal,
    interval: str = MONTHLY,
    discount_percent=None,
) -> Decimal:
    """Amount to charge for one billing cycle of ``monthly_price``."""
    price = Decimal(str(monthly_price or 0)).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    interval = normalize_billing_interval(interval)
    if interval == YEARLY:
        return yearly_amount(price, discount_percent)
    return price


def period_delta(interval: str = MONTHLY) -> timedelta:
    """Vigencia of one billing cycle."""
    interval = normalize_billing_interval(interval)
    days = YEARLY_PERIOD_DAYS if interval == YEARLY else MONTHLY_PERIOD_DAYS
    return timedelta(days=days)
