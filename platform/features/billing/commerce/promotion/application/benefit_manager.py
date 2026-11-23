"""Thin application wrappers over the pure domain promotion services.

These helpers adapt duck-typed inputs (ORM-like vouchers/subscriptions used in
tests and callers) to the ORM-free domain services in ``domain/services``.
They contain NO Django imports and NO persistence.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from ..domain.schemas import PlanSnapshot
from ..domain.services.benefit_window import build_benefit_window as _domain_build_window
from ..domain.services.eligibility import assert_plan_eligible as _domain_assert_plan_eligible
from ..domain.services.preview import compute_preview as _domain_compute_preview

logger = logging.getLogger('app.api')


def _to_snapshot(sub) -> PlanSnapshot:
    return PlanSnapshot(
        id=sub.id,
        name=getattr(sub, 'name', '') or '',
        code=getattr(sub, 'code', '') or '',
        price=Decimal(str(sub.price)),
    )


def _allowed_plan_ids(voucher) -> list:
    """Extract eligible plan ids without requiring the Django ORM.

    Prefers a schema-style ``subscription_ids`` attribute, then falls back to an
    ORM-like ``subscriptions`` manager (duck-typed ``values_list``).
    """
    ids = getattr(voucher, 'subscription_ids', None)
    if ids:
        return list(ids)
    subs = getattr(voucher, 'subscriptions', None)
    if subs is not None and hasattr(subs, 'values_list'):
        return list(subs.values_list('id', flat=True))
    return []


def build_benefit_window(*, months: int, start: datetime | None = None) -> tuple[datetime, datetime]:
    start = start or datetime.now(timezone.utc)
    return _domain_build_window(months=months, start=start)


def compute_preview(voucher, target_sub, *, current_sub=None, billing_interval='monthly', annual_discount_percent=None) -> tuple:
    """Return ``(original, final, discount, message)`` from duck-typed inputs."""
    return _domain_compute_preview(
        voucher_type=str(voucher.voucher_type),
        benefit_months=getattr(voucher, 'benefit_months', None),
        discount_percent=getattr(voucher, 'discount_percent', None),
        discount_duration_months=getattr(voucher, 'discount_duration_months', None),
        target=_to_snapshot(target_sub),
        billing_interval=billing_interval,
        annual_discount_percent=annual_discount_percent,
    )


def assert_plan_eligible(voucher, target_sub, *, current_sub=None) -> None:
    _domain_assert_plan_eligible(
        allowed_plan_ids=_allowed_plan_ids(voucher),
        target=_to_snapshot(target_sub),
        current=_to_snapshot(current_sub) if current_sub is not None else None,
    )
