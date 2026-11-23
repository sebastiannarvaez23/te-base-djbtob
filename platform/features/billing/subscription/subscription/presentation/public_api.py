"""Public catalog endpoint for subscription plans.

Lives separately from :mod:`api` to keep the public contract isolated
from the admin CRUD:

  * Different permission policy (no auth, no subscription gate).
  * Different serializer (``PublicSubscriptionSerializer`` strips
    operational metadata).
  * Different ordering (ascending by price for the wizard).

Consumed by the onboarding wizard (registration) and the marketing
pages. Anonymous traffic is intentional.
"""

from rest_framework.views import APIView

from core.decorators.response import wrap_response
from platform.features.billing.subscription.subscription.application.use_cases import (
    GetActiveSubscriptionsUseCase,
)
from platform.features.billing.subscription.subscription.infrastructure.repositories import (
    DjangoSubscriptionRepository,
)


# The public catalog deliberately exposes a narrow projection. Adding a
# field here is a public-API change — review carefully (admin metadata
# such as ``is_active``, ``created_at``, ``updated_at`` MUST stay out).
_PUBLIC_PLAN_FIELDS = (
    'id', 'name', 'price', 'currency', 'yearly_price', 'annual_discount_percent',
    'code', 'description', 'logo',
)


class PublicSubscriptionCatalogAPIView(APIView):
    """``GET /api/v1/subscriptions/`` — public list of active plans."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        plans = GetActiveSubscriptionsUseCase(
            DjangoSubscriptionRepository(),
        ).execute()
        data = [
            {k: v for k, v in p.model_dump(mode='json').items() if k in _PUBLIC_PLAN_FIELDS}
            for p in plans
        ]
        return wrap_response(data)
