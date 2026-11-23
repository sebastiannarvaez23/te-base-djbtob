"""Pure decision of the plan change a redemption implies.

Returns which plan (if any) must be activated and which plan (if any) must be
restored on a later revert. Mirrors the historic ``apply_subscription_effect``:

  * GIFT upgrade (current cheaper than target): activate target, remember the
    previous plan so it can be restored when the gift benefit ends.
  * DISCOUNT upgrade (current cheaper than target): activate target; no revert
    (the customer keeps the dearer plan and pays for it after the discount).
  * Same-plan gift / no current plan: no plan change.
"""

from typing import Optional
from uuid import UUID

from ..schemas import PlanSnapshot


def decide_plan_effect(
    *,
    voucher_type: str,
    target: PlanSnapshot,
    current: Optional[PlanSnapshot],
) -> tuple[Optional[UUID], Optional[UUID]]:
    """Return ``(activate_plan_id, previous_plan_id)``."""
    if voucher_type == 'GIFT' and current is not None and target.price > current.price:
        return target.id, current.id
    if voucher_type == 'DISCOUNT' and current is not None and target.price > current.price:
        return target.id, None
    return None, None
