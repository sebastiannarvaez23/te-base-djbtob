import uuid
from typing import Optional

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.access.functionalities.domain.interfaces import IFunctionalityRepository
from platform.features.security.access.functionalities.domain.schemas import (
    AssignFunctionalitySchema,
    CreateFunctionalitySchema,
    FunctionalitySchema,
    UpdateFunctionalitySchema,
)
from platform.features.security.access.functionalities.models import Functionality
from platform.features.security.access.modules.models import Module
from platform.features.security.catalog_order import category_rank


def _to_schema(obj: Functionality) -> FunctionalitySchema:
    return FunctionalitySchema.model_validate({
        'id':         obj.id,
        'module':     obj.module.code,
        'key':        obj.key,
        'label':      obj.label,
        'category':   obj.category,
        'offering':   obj.offering,
        'billing_mode': obj.billing_mode,
        'catalog_service_id': obj.catalog_service_id,
        'is_active':  obj.is_active,
        'created_at': obj.created_at,
        'updated_at': obj.updated_at,
    })


class DjangoFunctionalityRepository(IFunctionalityRepository):

    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        from django.db.models.functions import Lower

        qs = Functionality.objects.select_related('module').order_by(
            'module__order', category_rank(), Lower('label'), 'key',
        )
        f = query.filters
        if 'label' in f:
            qs = qs.filter(label__icontains=f['label'])
        if 'key' in f:
            qs = qs.filter(key__icontains=f['key'])
        if 'module' in f:
            qs = qs.filter(module__code=f['module'])
        if 'category' in f:
            qs = qs.filter(category=f['category'])
        if 'offering' in f:
            qs = qs.filter(offering=f['offering'])
        if 'billing_mode' in f:
            qs = qs.filter(billing_mode=f['billing_mode'])
        if 'is_active' in f:
            qs = qs.filter(is_active=bool(f['is_active']))
        total = qs.count()
        items = [_to_schema(func) for func in qs[query.offset: query.offset + query.limit]]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(items=items, total=total, page=query.page, page_size=query.page_size, total_pages=total_pages)

    def get_by_id(self, functionality_id: uuid.UUID) -> Optional[FunctionalitySchema]:
        try:
            obj = Functionality.objects.select_related('module').get(id=functionality_id)
            return _to_schema(obj)
        except Functionality.DoesNotExist:
            return None

    def create(self, data: CreateFunctionalitySchema) -> FunctionalitySchema:
        module = Module.objects.get(code=data.module)
        obj = Functionality.objects.create(
            key=data.key,
            label=data.label,
            category=data.category,
            module=module,
            offering=data.offering,
            billing_mode=data.billing_mode,
            catalog_service_id=data.catalog_service_id,
        )
        obj.refresh_from_db(fields=['module'])
        return _to_schema(obj)

    def update(self, functionality_id: uuid.UUID, data: UpdateFunctionalitySchema) -> Optional[FunctionalitySchema]:
        try:
            obj = Functionality.objects.select_related('module').get(id=functionality_id)
        except Functionality.DoesNotExist:
            return None
        update_data = data.model_dump(exclude_unset=True)
        update_data = {key: value for key, value in update_data.items() if value is not None or key == 'catalog_service_id'}
        if 'module' in update_data:
            obj.module = Module.objects.get(code=update_data.pop('module'))
        for field, value in update_data.items():
            setattr(obj, field, value)
        obj.save()
        if 'is_active' in update_data:
            from core.access.invalidation import invalidate_on_functionality_change
            invalidate_on_functionality_change(obj.id)
        return _to_schema(obj)

    def delete(self, functionality_id: uuid.UUID) -> bool:
        try:
            Functionality.objects.get(id=functionality_id).delete()
            return True
        except Functionality.DoesNotExist:
            return False

    def toggle(self, functionality_id: uuid.UUID) -> Optional[FunctionalitySchema]:
        try:
            obj = Functionality.objects.select_related('module').get(id=functionality_id)
        except Functionality.DoesNotExist:
            return None
        obj.is_active = not obj.is_active
        obj.save()
        from core.access.invalidation import invalidate_on_functionality_change
        invalidate_on_functionality_change(obj.id)
        return _to_schema(obj)

    def assign_module(self, functionality_id: uuid.UUID, data: AssignFunctionalitySchema) -> Optional[FunctionalitySchema]:
        try:
            obj = Functionality.objects.select_related('module').get(id=functionality_id)
        except Functionality.DoesNotExist:
            return None
        obj.module = Module.objects.get(code=data.module)
        obj.save()
        return _to_schema(obj)
