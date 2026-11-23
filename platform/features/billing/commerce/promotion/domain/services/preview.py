"""Pure preview/pricing composition for a voucher against a target plan."""

from decimal import Decimal
from typing import Optional

from platform.features.billing.commerce.promotion.application.pricing import apply_discount, gift_final_amount
from platform.features.billing.subscription.subscription.domain.billing_cycle import MONTHLY, charge_amount

from ..schemas import PlanSnapshot


def compute_preview(
    *,
    voucher_type: str,
    benefit_months: Optional[int],
    discount_percent: Optional[Decimal],
    discount_duration_months: Optional[int],
    target: PlanSnapshot,
    billing_interval: str = MONTHLY,
    annual_discount_percent: Optional[Decimal] = None,
) -> tuple[Decimal, Decimal, Decimal, str]:
    """Return ``(original, final, discount, message)``.

    ``original`` is the charge amount of the selected billing cycle (monthly
    list price, or yearly = 12 × monthly with the annual discount). Promo %
    then applies on top of that cycle amount.
    """
    original = charge_amount(target.price, billing_interval, annual_discount_percent)
    if voucher_type == 'GIFT':
        final, discount = gift_final_amount(original)
        msg = f'Suscripción {target.name} gratis por {benefit_months} mes(es).'
        return original, final, discount, msg
    final, discount = apply_discount(original, discount_percent)
    msg = (
        f'{discount_percent}% de descuento en {target.name} '
        f'por {discount_duration_months} renovación(es).'
    )
    return original, final, discount, msg
