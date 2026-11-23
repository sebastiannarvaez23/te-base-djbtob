import uuid
from typing import List, Optional
from ..domain.interfaces import ISubscriptionLimitRepository
from ..domain.schemas import CreateSubscriptionLimitSchema, SubscriptionLimitSchema, UpdateSubscriptionLimitSchema
from ..models import SubscriptionLimit
from core.access.subscription import SubscriptionCache


def _to_schema(obj: SubscriptionLimit) -> SubscriptionLimitSchema:
    return SubscriptionLimitSchema(
        id=obj.id,
        subscription_id=obj.subscription_id,
        functionality_id=obj.functionality_id,
        subscription_name=obj.subscription.name,
        functionality_key=obj.functionality.key,
        functionality_label=obj.functionality.label,
        functionality_module_code=obj.functionality.module.code,
        name=obj.name,
        max_value=obj.max_value,
        validation_type=obj.validation_type,
        window_hours=obj.window_hours,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


class DjangoSubscriptionLimitRepository(ISubscriptionLimitRepository):

    def _qs(self):
        return SubscriptionLimit.objects.select_related('subscription', 'functionality', 'functionality__module')

    def _apply_filters(self, qs, filters: dict | None):
        f = filters or {}
        if 'subscription_id' in f:
            qs = qs.filter(subscription_id=f['subscription_id'])
        if 'functionality_id' in f:
            qs = qs.filter(functionality_id=f['functionality_id'])
        if 'validation_type' in f:
            qs = qs.filter(validation_type=f['validation_type'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        return qs

    def get_all(self, filters: dict | None = None) -> List[SubscriptionLimitSchema]:
        qs = self._apply_filters(
            self._qs().order_by('subscription__name', 'functionality__key'),
            filters,
        )
        return [_to_schema(obj) for obj in qs]

    def get_by_subscription(
        self, subscription_id: uuid.UUID, filters: dict | None = None,
    ) -> List[SubscriptionLimitSchema]:
        qs = self._apply_filters(
            self._qs().filter(subscription_id=subscription_id).order_by('functionality__key'),
            filters,
        )
        return [_to_schema(obj) for obj in qs]

    def get_by_id(self, id: uuid.UUID) -> Optional[SubscriptionLimitSchema]:
        try:
            return _to_schema(self._qs().get(id=id))
        except SubscriptionLimit.DoesNotExist:
            return None

    def create(self, data: CreateSubscriptionLimitSchema) -> SubscriptionLimitSchema:
        obj = SubscriptionLimit.objects.create(
            subscription_id=data.subscription_id,
            functionality_id=data.functionality_id,
            name=data.name,
            max_value=data.max_value,
            validation_type=data.validation_type,
            window_hours=data.window_hours,
        )
        SubscriptionCache.invalidate_subscription(str(data.subscription_id))
        return _to_schema(self._qs().get(id=obj.id))

    def update(self, id: uuid.UUID, data: UpdateSubscriptionLimitSchema) -> Optional[SubscriptionLimitSchema]:
        try:
            obj = self._qs().get(id=id)
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(obj, field, value)
            obj.save()
            SubscriptionCache.invalidate_subscription(str(obj.subscription_id))
            return _to_schema(obj)
        except SubscriptionLimit.DoesNotExist:
            return None

    def delete(self, id: uuid.UUID) -> bool:
        try:
            obj = SubscriptionLimit.objects.get(id=id)
            subscription_id = str(obj.subscription_id)
            obj.delete()
            SubscriptionCache.invalidate_subscription(subscription_id)
            return True
        except SubscriptionLimit.DoesNotExist:
            return False
