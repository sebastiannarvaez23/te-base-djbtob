"""Benefit lifecycle use cases (revert expired gift upgrades).

Pure orchestration over ports: the repository lists the gift benefits whose
window elapsed (as ``ActiveBenefitSchema``) and the plan catalog restores the
previous plan. No Django models here.
"""

from datetime import datetime

from ..domain.interfaces import IPlanCatalogPort, IPromotionVoucherRepository


def revert_expired_gift_benefits(
    repo: IPromotionVoucherRepository,
    plan_catalog: IPlanCatalogPort,
    *,
    now: datetime,
) -> int:
    """Restore the previous plan for gift upgrades whose window elapsed.

    ``list_gift_benefits_due_for_revert`` already filters to ACTIVE gift
    benefits that carry a ``previous_subscription_id`` and are past ``now``.
    """
    reverted = 0
    for benefit in repo.list_gift_benefits_due_for_revert(now=now):
        if benefit.previous_subscription_id is not None:
            plan_catalog.activate_plan(
                benefit.company_id,
                benefit.previous_subscription_id,
                billing_interval=plan_catalog.get_company_billing_interval(benefit.company_id),
            )
        repo.complete_benefit(benefit.id)
        reverted += 1
    return reverted
