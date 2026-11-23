import uuid
from typing import List, Optional

from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException
from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.catalog_order import apply_order, next_order
from platform.features.security.access.modules.domain.interfaces import IModuleRepository
from platform.features.security.access.modules.domain.schemas import (
    ModuleSchema,
    CreateModuleSchema,
    UpdateModuleSchema,
)
from platform.features.security.access.modules.models import Module
from platform.features.security.access.sections.models import Section


def _ordered_modules():
    """Default catalog order: section order, then the order the user set."""
    return (
        Module.objects
        .select_related('section')
        .order_by('section__order', 'order', 'name')
    )


def _to_module_schema(module: Module) -> ModuleSchema:
    schema = ModuleSchema.model_validate(module)
    section = getattr(module, 'section', None)
    order = getattr(section, 'order', None) if section is not None else None
    if not isinstance(order, int) or not hasattr(schema, 'model_copy'):
        return schema
    return schema.model_copy(update={
        'section_code': getattr(section, 'code', '') or '',
        'section_name': getattr(section, 'name', '') or '',
        'section_order': order,
    })


def _ensure_unique_module_code(code: str, exclude_id: Optional[uuid.UUID] = None) -> None:
    qs = Module.objects.filter(code=code)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ConflictException(
            AppErrorCode.MODULE_DUPLICATE_CODE,
            override_detail=f"A module with code '{code}' already exists.",
        )


def _table_exists(table_name: str) -> bool:
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = current_schema()"
            "  AND table_name = %s"
            ")",
            [table_name],
        )
        return bool(cursor.fetchone()[0])


def _functionality_ids(module_id: uuid.UUID) -> list[uuid.UUID]:
    from platform.features.security.access.functionalities.models import Functionality

    return list(
        Functionality.objects.filter(module_id=module_id).values_list('id', flat=True),
    )


def _purge_tenant_role_grants(module_code: str, func_ids: list[uuid.UUID]) -> None:
    from django_tenants.utils import get_tenant_model, schema_context

    Tenant = get_tenant_model()
    for tenant in Tenant.objects.exclude(schema_name='public'):
        with schema_context(tenant.schema_name):
            if _table_exists('security_rol_features') and func_ids:
                from client.features.security.lifecycle.registration.models import RolFeature
                RolFeature.objects.filter(feature_id__in=func_ids).delete()
            if _table_exists('security_rol_modules'):
                from client.features.security.lifecycle.registration.models import RolModule
                RolModule.objects.filter(module_code=module_code).delete()


def _purge_public_dependents(module: Module, func_ids: list[uuid.UUID]) -> None:
    from platform.features.billing.subscription.subscription.models import (
        SubscriptionFunctionality,
        SubscriptionModule,
    )
    from platform.features.billing.subscription.subscription_limit.models import SubscriptionLimit
    from platform.features.security.access.functionalities.models import Functionality
    from platform.features.support.incidents.incident.models import Incident

    if func_ids:
        SubscriptionFunctionality.objects.filter(functionality_id__in=func_ids).delete()
        SubscriptionLimit.objects.filter(functionality_id__in=func_ids).delete()
        Incident.objects.filter(functionality_id__in=func_ids).update(functionality=None)

    Incident.objects.filter(module_id=module.id).update(module=None)
    SubscriptionModule.objects.filter(module_code=module.code).delete()
    Functionality.objects.filter(module_id=module.id).delete()


class DjangoModuleRepository(IModuleRepository):

    def get_all(self, filters: dict | None = None) -> List[ModuleSchema]:
        qs = _ordered_modules()
        f = filters or {}
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'section_id' in f:
            qs = qs.filter(section_id=f['section_id'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        return [_to_module_schema(m) for m in qs]

    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        qs = _ordered_modules()
        f = query.filters
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'section_id' in f:
            qs = qs.filter(section_id=f['section_id'])
        if 'is_active' in f:
            qs = qs.filter(is_active=bool(f['is_active']))
        total = qs.count()
        items = [_to_module_schema(m) for m in qs[query.offset: query.offset + query.limit]]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(items=items, total=total, page=query.page, page_size=query.page_size, total_pages=total_pages)

    def get_by_id(self, module_id: uuid.UUID) -> Optional[ModuleSchema]:
        try:
            return _to_module_schema(Module.objects.select_related('section').get(id=module_id))
        except Module.DoesNotExist:
            return None

    def create(self, data: CreateModuleSchema) -> ModuleSchema:
        section = Section.objects.get(id=data.section_id)
        _ensure_unique_module_code(data.code)
        try:
            module = Module.objects.create(
                code=data.code,
                name=data.name,
                description=data.description,
                icon=data.icon,
                route=data.route,
                section=section,
                order=data.order or next_order(Module, section_id=data.section_id),
                is_sidebar=data.is_sidebar,
                offering=data.offering,
                billing_mode=data.billing_mode,
                catalog_service_id=data.catalog_service_id,
            )
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.MODULE_DUPLICATE_CODE,
                override_detail=f"A module with code '{data.code}' already exists.",
            )
        return _to_module_schema(module)

    def update(self, module_id: uuid.UUID, data: UpdateModuleSchema) -> Optional[ModuleSchema]:
        try:
            module = Module.objects.select_related('section').get(id=module_id)
        except Module.DoesNotExist:
            return None
        update_data = data.model_dump(exclude_unset=True)
        update_data = {
            key: value for key, value in update_data.items()
            if value is not None or key == 'catalog_service_id'
        }
        if 'section_id' in update_data:
            section = Section.objects.get(id=update_data.pop('section_id'))
            module.section = section
        for field, value in update_data.items():
            setattr(module, field, value)
        try:
            module.save()
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.MODULE_DUPLICATE_CODE,
                override_detail=f"A module with code '{module.code}' already exists.",
            )
        if 'is_active' in update_data:
            from core.access.invalidation import invalidate_on_module_change
            invalidate_on_module_change(module.id)
        return _to_module_schema(module)

    def delete(self, module_id: uuid.UUID) -> bool:
        from django.db import transaction

        try:
            module = Module.objects.get(id=module_id)
        except Module.DoesNotExist:
            return False

        if not _table_exists('security_features'):
            Module.objects.filter(id=module_id).delete()
            return True

        func_ids = _functionality_ids(module.id)
        _purge_tenant_role_grants(module.code, func_ids)
        with transaction.atomic():
            _purge_public_dependents(module, func_ids)
            module.delete()
        return True

    def toggle(self, module_id: uuid.UUID) -> Optional[ModuleSchema]:
        try:
            module = Module.objects.select_related('section').get(id=module_id)
        except Module.DoesNotExist:
            return None
        module.is_active = not module.is_active
        module.save()
        from core.access.invalidation import invalidate_on_module_change
        invalidate_on_module_change(module.id)
        return _to_module_schema(module)

    def reorder(self, ids: list[uuid.UUID]) -> int:
        return apply_order(Module, ids)
