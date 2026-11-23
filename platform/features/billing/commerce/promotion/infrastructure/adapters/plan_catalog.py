"""Plan catalog adapter — reads subscription plans as ORM-free PlanSnapshots."""

import uuid
from typing import Optional

from core.errors import AppErrorCode, AppException

from platform.features.billing.commerce.promotion.domain.interfaces import IPlanCatalogPort
from platform.features.billing.commerce.promotion.domain.schemas import PlanSnapshot


def _to_snapshot(sub) -> PlanSnapshot:
    return PlanSnapshot(
        id=sub.id,
        name=sub.name,
        code=getattr(sub, 'code', '') or '',
        price=sub.price,
    )


class DjangoPlanCatalog(IPlanCatalogPort):

    def get_active_plan(self, subscription_id: uuid.UUID) -> PlanSnapshot:
        from platform.features.billing.subscription.subscription.models import Subscription
        try:
            sub = Subscription.objects.get(id=subscription_id, is_active=True)
        except Subscription.DoesNotExist:
            raise AppException(AppErrorCode.PROMO_PLAN_INELIGIBLE)
        return _to_snapshot(sub)

    def get_company_active_plan(self, company_id: uuid.UUID) -> Optional[PlanSnapshot]:
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        from platform.features.billing.subscription.subscription.models import Subscription

        plan_id = DjangoSubscriptionRepository().active_plan_id(company_id)
        if plan_id is None:
            return None
        try:
            sub = Subscription.objects.get(id=plan_id)
        except Subscription.DoesNotExist:
            return None
        return _to_snapshot(sub)

    def get_company_billing_interval(self, company_id: uuid.UUID) -> str:
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        return DjangoSubscriptionRepository().active_billing_interval(company_id)

    def get_annual_discount_percent(self) -> 'Decimal':
        from decimal import Decimal
        from platform.features.billing.subscription.subscription.infrastructure.billing_settings import (
            live_annual_discount_percent,
        )
        return live_annual_discount_percent() or Decimal('15')

    def activate_plan(self, company_id: uuid.UUID, subscription_id: uuid.UUID, *, billing_interval: str = 'monthly') -> None:
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        DjangoSubscriptionRepository().activate_plan(
            company_id, subscription_id, billing_interval=billing_interval,
        )

    def list_all_company_ids(self) -> list[uuid.UUID]:
        from platform.features.company.tenant.company.models import Company
        return list(Company.objects.values_list('id', flat=True))
