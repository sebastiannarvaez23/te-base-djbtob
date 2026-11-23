"""Django adapter for the onboarding plan catalog port."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from client.features.security.lifecycle.onboarding.domain.interfaces import IOnboardingPlanCatalog
from client.features.security.lifecycle.onboarding.domain.schemas import OnboardingPlanQuote


class DjangoOnboardingPlanCatalog(IOnboardingPlanCatalog):

    def get_active_plan(self, subscription_id: UUID) -> Optional[OnboardingPlanQuote]:
        from platform.features.billing.subscription.subscription.models import Subscription
        try:
            sub = Subscription.objects.get(id=subscription_id, is_active=True)
        except Subscription.DoesNotExist:
            return None
        return OnboardingPlanQuote(
            id=sub.id,
            name=sub.name,
            price=Decimal(str(sub.price or 0)),
            currency=(getattr(sub, 'currency', None) or 'USD').strip().upper() or 'USD',
        )

    def annual_discount_percent(self) -> Decimal:
        from platform.features.billing.subscription.subscription.infrastructure.billing_settings import (
            live_annual_discount_percent,
        )
        return live_annual_discount_percent()
