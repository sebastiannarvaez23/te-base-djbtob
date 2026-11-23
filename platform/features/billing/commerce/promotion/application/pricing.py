from decimal import Decimal, ROUND_HALF_UP

_TWOPLACES = Decimal('0.01')


def apply_discount(amount: Decimal, discount_percent: Decimal) -> tuple[Decimal, Decimal]:
    """Return (final_amount, discount_amount)."""
    original = Decimal(str(amount))
    percent = Decimal(str(discount_percent))
    if percent <= 0:
        return original, Decimal('0')
    if percent >= 100:
        return Decimal('0'), original
    discount = (original * percent / Decimal('100')).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    final_amount = (original - discount).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    return final_amount, discount


def gift_final_amount(plan_price: Decimal) -> tuple[Decimal, Decimal]:
    original = Decimal(str(plan_price))
    return Decimal('0'), original
