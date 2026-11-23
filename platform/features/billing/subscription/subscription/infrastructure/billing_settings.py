"""Live annual-discount parameter. Domain math stays DB-free."""
from decimal import Decimal, ROUND_HALF_UP

from platform.features.billing.subscription.subscription.domain.billing_cycle import (
    DEFAULT_ANNUAL_DISCOUNT_PERCENT,
    coerce_annual_discount_percent,
)
from platform.features.billing.subscription.subscription.models import BillingSettings

_TWOPLACES = Decimal('0.01')


def live_annual_discount_percent() -> Decimal:
    """Read the admin-configured percent. Missing row / DB errors → default."""
    try:
        row = (
            BillingSettings.objects
            .filter(singleton_key=BillingSettings.SINGLETON_KEY)
            .values_list('annual_discount_percent', flat=True)
            .first()
        )
        if row is None:
            return DEFAULT_ANNUAL_DISCOUNT_PERCENT
        return coerce_annual_discount_percent(row)
    except Exception:
        return DEFAULT_ANNUAL_DISCOUNT_PERCENT


def persist_annual_discount_percent(percent: Decimal) -> Decimal:
    """Create or update the singleton row. Caller must have validated 0–100."""
    value = Decimal(str(percent)).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    row, created = BillingSettings.objects.get_or_create(
        singleton_key=BillingSettings.SINGLETON_KEY,
        defaults={'annual_discount_percent': value},
    )
    if not created:
        row.annual_discount_percent = value
        row.save(update_fields=['annual_discount_percent', 'updated_at'])
    return coerce_annual_discount_percent(row.annual_discount_percent)
