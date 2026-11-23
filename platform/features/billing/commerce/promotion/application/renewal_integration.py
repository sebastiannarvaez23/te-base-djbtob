"""Renewal integration with active promotion benefits.

Pure orchestration over the repository port + the ``compute_renewal_charge``
domain service. No Django models: the repository returns ``ActiveBenefitSchema``
and the decision (amount/metadata/skip) is made by the domain service.
"""

from datetime import datetime, timezone
from decimal import Decimal

from ..domain.interfaces import IPromotionVoucherRepository
from ..domain.services.renewal import compute_renewal_charge


def get_renewal_charge_amount(
    repo: IPromotionVoucherRepository,
    company_id,
    plan_price: Decimal,
    *,
    plan_id=None,
):
    """Return ``(amount, metadata, skip_charge)`` for renewing ``plan_id``.

    Benefits only apply when they target the plan being renewed (``plan_id``).
    """
    benefit = repo.get_active_benefit(company_id, subscription_id=plan_id)
    decision = compute_renewal_charge(
        benefit=benefit, plan_price=plan_price, now=datetime.now(timezone.utc),
    )
    return decision.amount, decision.metadata, decision.skip_charge


def after_successful_renewal_charge(
    repo: IPromotionVoucherRepository,
    company_id,
    *,
    plan_id=None,
) -> None:
    benefit = repo.get_active_benefit(company_id, subscription_id=plan_id)
    if benefit is None:
        return
    if benefit.voucher_type == 'DISCOUNT':
        repo.decrement_discount_cycle(benefit.id)
