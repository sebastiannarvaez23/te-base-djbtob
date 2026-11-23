import uuid
from typing import List
from ..domain.interfaces import ISubscriptionModuleRepository
from ..domain.schemas import SubscriptionModuleSchema, UpdateSubscriptionModulesSchema
from platform.features.billing.subscription.subscription.models import Subscription, SubscriptionModule
from core.access.subscription import SubscriptionCache


def _to_schema(obj: SubscriptionModule) -> SubscriptionModuleSchema:
    return SubscriptionModuleSchema(
        id=obj.id,
        subscription_id=obj.subscription_id,
        subscription_name=obj.subscription.name,
        module_code=obj.module_code,
    )


class DjangoSubscriptionModuleRepository(ISubscriptionModuleRepository):

    def _qs(self):
        return SubscriptionModule.objects.select_related('subscription')

    def get_by_subscription(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionModuleSchema]:
        qs = self._qs().filter(subscription_id=subscription_id).order_by('module_code')
        f = filters or {}
        if 'module_code' in f:
            qs = qs.filter(module_code__icontains=f['module_code'])
        if 'q' in f:
            qs = qs.filter(module_code__icontains=f['q'])
        return [_to_schema(obj) for obj in qs]

    def update_modules(self, subscription_id: uuid.UUID, data: UpdateSubscriptionModulesSchema) -> List[SubscriptionModuleSchema]:
        try:
            subscription = Subscription.objects.get(id=subscription_id)
        except Subscription.DoesNotExist:
            return None

        SubscriptionModule.objects.filter(subscription=subscription).delete()
        if data.module_codes:
            SubscriptionModule.objects.bulk_create([
                SubscriptionModule(subscription=subscription, module_code=code)
                for code in data.module_codes
            ])

        # Invalidar caché de empresas que usan este plan
        SubscriptionCache.invalidate_subscription(str(subscription_id))

        return self.get_by_subscription(subscription_id)
