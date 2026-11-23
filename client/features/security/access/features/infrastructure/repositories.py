from typing import Optional
from uuid import UUID

from client.features.security.access.features.domain.interfaces import IFeatureRepository
from client.features.security.access.features.domain.schemas import (
    CreateFeatureSchema, FeatureSchema, UpdateFeatureSchema,
)
from platform.features.security.access.functionalities.models import Functionality
from platform.features.security.access.modules.models import Module


def _to_feature_schema(obj: Functionality) -> FeatureSchema:
    return FeatureSchema.model_validate({
        'id':        obj.id,
        'module':    obj.module.code,
        'key':       obj.key,
        'label':     obj.label,
        'category':  obj.category,
        'is_active': obj.is_active,
    })


class DjangoFeatureRepository(IFeatureRepository):
    def get_all(self, module: Optional[str] = None) -> list[FeatureSchema]:
        qs = Functionality.objects.select_related('module').all()
        if module:
            qs = qs.filter(module__code=module)
        return [_to_feature_schema(f) for f in qs.order_by('module__code', 'key')]

    def get_by_id(self, feature_id: UUID) -> Optional[FeatureSchema]:
        try:
            obj = Functionality.objects.select_related('module').get(id=feature_id)
            return _to_feature_schema(obj)
        except Functionality.DoesNotExist:
            return None

    def create(self, data: CreateFeatureSchema) -> FeatureSchema:
        module = Module.objects.get(code=data.module)
        obj = Functionality.objects.create(
            key=data.key,
            label=data.label,
            category=data.category,
            module=module,
        )
        obj.refresh_from_db(fields=['module'])
        return _to_feature_schema(obj)

    def delete(self, feature_id: UUID) -> bool:
        try:
            Functionality.objects.get(id=feature_id).delete()
            return True
        except Functionality.DoesNotExist:
            return False

    def update(self, feature_id: UUID, data: UpdateFeatureSchema) -> Optional[FeatureSchema]:
        try:
            obj = Functionality.objects.select_related('module').get(id=feature_id)
        except Functionality.DoesNotExist:
            return None
        if data.label is not None:
            obj.label = data.label
        if data.category is not None:
            obj.category = data.category
        if data.is_active is not None:
            obj.is_active = data.is_active
        obj.save()
        return _to_feature_schema(obj)
