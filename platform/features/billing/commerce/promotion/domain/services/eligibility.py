"""Pure eligibility rules for redeeming/validating a voucher (no Django)."""

from datetime import datetime
from typing import Iterable, Optional
from uuid import UUID

from core.errors import AppErrorCode, AppException, ConflictException

from ..schemas import PlanSnapshot


def assert_redeemable(*, status: str, valid_from: datetime, valid_until: datetime, now: datetime) -> None:
    if status == 'ACTIVE':
        if valid_from > now or valid_until < now:
            raise AppException(AppErrorCode.PROMO_OUT_OF_WINDOW)
        return
    if status == 'REDEEMED':
        raise ConflictException(AppErrorCode.PROMO_ALREADY_CONSUMED)
    raise AppException(AppErrorCode.PROMO_NOT_ACTIVE)


def assert_scope(*, scope: str, voucher_company_id: Optional[UUID], company_id: Optional[UUID]) -> None:
    if company_id is None:
        return
    if scope == 'COMPANY' and voucher_company_id != company_id:
        raise AppException(AppErrorCode.PROMO_SCOPE_DENIED)


def assert_plan_eligible(
    *,
    allowed_plan_ids: Iterable[UUID],
    target: PlanSnapshot,
    current: Optional[PlanSnapshot],
) -> None:
    if target.id not in set(allowed_plan_ids):
        raise AppException(AppErrorCode.PROMO_PLAN_INELIGIBLE)
    if current is not None and target.price < current.price:
        raise AppException(AppErrorCode.PROMO_PLAN_INELIGIBLE)
