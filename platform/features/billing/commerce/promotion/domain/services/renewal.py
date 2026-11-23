"""Pure renewal-charge decision given an active benefit (no Django)."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from platform.features.billing.commerce.promotion.application.pricing import apply_discount

from ..schemas import ActiveBenefitSchema, RenewalChargeDecision


def compute_renewal_charge(
    *,
    benefit: Optional[ActiveBenefitSchema],
    plan_price: Decimal,
    now: datetime,
) -> RenewalChargeDecision:
    """Decide the amount (and email/annex metadata) for renewing a plan.

    Benefits only apply when they target the plan being renewed — the caller is
    responsible for passing the benefit that matches the plan (or ``None``).
    """
    if benefit is None:
        return RenewalChargeDecision(amount=plan_price, metadata={}, skip_charge=False)

    if benefit.voucher_type == 'GIFT':
        if now < benefit.benefit_end:
            serial = benefit.voucher_serial
            return RenewalChargeDecision(
                amount=Decimal('0'),
                skip_charge=True,
                metadata={
                    'promotion_benefit_id': str(benefit.id),
                    'promotion_serial': serial,
                    'voucher_type': 'GIFT',
                    'original_amount': str(plan_price),
                    'discount_amount': str(plan_price),
                    'email_context': {
                        'promotion_serial': serial,
                        'promotion_voucher_type': 'GIFT',
                        'promotion_original_amount': float(plan_price),
                        'promotion_discount_amount': float(plan_price),
                    },
                },
            )
        return RenewalChargeDecision(amount=plan_price, metadata={}, skip_charge=False)

    if (
        benefit.voucher_type == 'DISCOUNT'
        and benefit.remaining_discount_cycles
        and benefit.remaining_discount_cycles > 0
        and benefit.discount_percent
    ):
        final, discount = apply_discount(plan_price, benefit.discount_percent)
        serial = benefit.voucher_serial
        return RenewalChargeDecision(
            amount=final,
            skip_charge=False,
            metadata={
                'promotion_benefit_id': str(benefit.id),
                'promotion_serial': serial,
                'voucher_type': 'DISCOUNT',
                'original_amount': str(plan_price),
                'discount_amount': str(discount),
                'email_context': {
                    'promotion_serial': serial,
                    'promotion_voucher_type': 'DISCOUNT',
                    'promotion_original_amount': float(plan_price),
                    'promotion_discount_amount': float(discount),
                },
            },
        )

    return RenewalChargeDecision(amount=plan_price, metadata={}, skip_charge=False)
