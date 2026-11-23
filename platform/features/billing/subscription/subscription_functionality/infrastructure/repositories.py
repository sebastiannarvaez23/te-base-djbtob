import uuid
from typing import List, Optional
from ..domain.interfaces import ISubscriptionFunctionalityRepository
from ..domain.schemas import SubscriptionFunctionalitySchema, UpdateSubscriptionFunctionalitiesSchema
from platform.features.billing.subscription.subscription.models import Subscription, SubscriptionFunctionality
from django.db import transaction

from platform.features.security.access.functionalities.models import Functionality
from core.access.subscription import SubscriptionCache


def _to_schema(obj: SubscriptionFunctionality) -> SubscriptionFunctionalitySchema:
    return SubscriptionFunctionalitySchema(
        id=obj.id,
        subscription_id=obj.subscription_id,
        subscription_name=obj.subscription.name,
        functionality_key=obj.functionality.key,
        functionality_label=obj.functionality.label,
        functionality_module_code=obj.functionality.module.code,
    )


class DjangoSubscriptionFunctionalityRepository(ISubscriptionFunctionalityRepository):

    def _qs(self):
        return SubscriptionFunctionality.objects.select_related('subscription', 'functionality', 'functionality__module')

    def get_by_subscription(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionFunctionalitySchema]:
        from django.db.models import Q

        qs = self._qs().filter(subscription_id=subscription_id).order_by('functionality__key')
        f = filters or {}
        if 'functionality_key' in f:
            qs = qs.filter(functionality__key__icontains=f['functionality_key'])
        if 'q' in f:
            q = f['q']
            qs = qs.filter(
                Q(functionality__key__icontains=q) | Q(functionality__label__icontains=q)
            )
        return [_to_schema(obj) for obj in qs]

    def update_functionalities(self, subscription_id: uuid.UUID, data: UpdateSubscriptionFunctionalitiesSchema) -> Optional[List[SubscriptionFunctionalitySchema]]:
        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return None

        valid_functionalities = list(
            Functionality.objects.filter(key__in=data.functionality_keys, is_active=True)
        )

        with transaction.atomic():
            SubscriptionFunctionality.objects.filter(subscription=subscription).delete()
            if valid_functionalities:
                SubscriptionFunctionality.objects.bulk_create([
                    SubscriptionFunctionality(subscription=subscription, functionality=func)
                    for func in valid_functionalities
                ])

        # Invalidar caché de empresas que usan este plan
        SubscriptionCache.invalidate_subscription(str(subscription_id))

        return self.get_by_subscription(subscription_id)
