import uuid
from typing import List, Optional

from django.db import IntegrityError

from core.errors import AppErrorCode, ConflictException
from platform.features.security.access.roles.domain.catalog_schemas import (
    AdminFeatureSchema,
    AdminModuleSchema,
    AdminSectionSchema,
    CreateAdminFeatureSchema,
    CreateAdminModuleSchema,
    CreateAdminSectionSchema,
    PaginatedAdminFeaturesSchema,
    PaginatedAdminModulesSchema,
    UpdateAdminFeatureSchema,
    UpdateAdminModuleSchema,
    UpdateAdminSectionSchema,
)
from platform.features.security.catalog_order import apply_order, category_rank, next_order
from platform.features.security.access.roles.domain.catalog_interfaces import IAdminCatalogRepository
from platform.features.security.access.roles.models import AdminFeature, AdminModule, AdminSection


def _section_schema(section: AdminSection) -> AdminSectionSchema:
    return AdminSectionSchema(
        id=section.id,
        code=section.code,
        name=section.name,
        icon=section.icon or '',
        order=section.order,
        is_active=section.is_active,
    )


def _module_schema(module: AdminModule) -> AdminModuleSchema:
    return AdminModuleSchema(
        id=module.id,
        code=module.code,
        name=module.name,
        description=module.description or '',
        icon=module.icon,
        route=module.route,
        section_id=module.section_id,
        section_code=module.section.code,
        section_name=module.section.name,
        section_order=module.section.order,
        order=module.order,
        is_sidebar=module.is_sidebar,
        is_active=module.is_active,
        created_at=module.created_at,
        updated_at=module.updated_at,
    )


def _feature_schema(feature: AdminFeature) -> AdminFeatureSchema:
    return AdminFeatureSchema(
        id=feature.id,
        module=feature.module.code,
        key=feature.key,
        label=feature.label,
        category=feature.category,
        is_active=feature.is_active,
    )


def _ensure_unique_admin_section_code(code: str, exclude_id: Optional[uuid.UUID] = None) -> None:
    qs = AdminSection.objects.filter(code=code)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ConflictException(
            AppErrorCode.SECTION_DUPLICATE_CODE,
            override_detail=f"A section with code '{code}' already exists.",
        )


def _ensure_unique_admin_module_code(code: str, exclude_id: Optional[uuid.UUID] = None) -> None:
    qs = AdminModule.objects.filter(code=code)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ConflictException(
            AppErrorCode.MODULE_DUPLICATE_CODE,
            override_detail=f"A module with code '{code}' already exists.",
        )


def _ensure_unique_admin_feature_key(key: str, exclude_id: Optional[uuid.UUID] = None) -> None:
    qs = AdminFeature.objects.filter(key=key)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ConflictException(
            AppErrorCode.FUNC_DUPLICATE_KEY,
            override_detail=f"A functionality with key '{key}' already exists.",
        )


class DjangoAdminCatalogRepository(IAdminCatalogRepository):

    # ── Sections ──────────────────────────────────────────────────────────────

    def list_sections(self, filters: dict | None = None) -> List[AdminSectionSchema]:
        from django.db.models import Q

        qs = AdminSection.objects.all().order_by('order', 'name')
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        return [_section_schema(s) for s in qs]

    def create_section(self, data: CreateAdminSectionSchema) -> AdminSectionSchema:
        _ensure_unique_admin_section_code(data.code)
        try:
            section = AdminSection.objects.create(
                code=data.code,
                name=data.name,
                icon=data.icon or '',
                order=data.order or next_order(AdminSection),
                is_active=True,
            )
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.SECTION_DUPLICATE_CODE,
                override_detail=f"A section with code '{data.code}' already exists.",
            )
        return _section_schema(section)

    def update_section(self, section_id: uuid.UUID, data: UpdateAdminSectionSchema) -> Optional[AdminSectionSchema]:
        try:
            section = AdminSection.objects.get(id=section_id)
        except AdminSection.DoesNotExist:
            return None
        payload = data.model_dump(exclude_none=True)
        if 'code' in payload:
            _ensure_unique_admin_section_code(payload['code'], exclude_id=section_id)
        for field, value in payload.items():
            setattr(section, field, value)
        try:
            section.save()
        except IntegrityError:
            code = payload.get('code', section.code)
            raise ConflictException(
                AppErrorCode.SECTION_DUPLICATE_CODE,
                override_detail=f"A section with code '{code}' already exists.",
            )
        return _section_schema(section)

    def toggle_section(self, section_id: uuid.UUID) -> Optional[AdminSectionSchema]:
        try:
            section = AdminSection.objects.get(id=section_id)
        except AdminSection.DoesNotExist:
            return None
        section.is_active = not section.is_active
        section.save(update_fields=['is_active'])
        return _section_schema(section)

    def delete_section(self, section_id: uuid.UUID) -> bool:
        deleted, _ = AdminSection.objects.filter(id=section_id).delete()
        return deleted > 0

    def reorder_sections(self, ids: list[uuid.UUID]) -> int:
        return apply_order(AdminSection, ids)

    # ── Modules ───────────────────────────────────────────────────────────────

    def list_modules(self, page: int = 0, page_size: int = 200) -> PaginatedAdminModulesSchema:
        qs = AdminModule.objects.select_related('section').order_by('section__order', 'order', 'name')
        total = qs.count()
        total_pages = (total + page_size - 1) // page_size if page_size else 1
        offset = page * page_size
        items = [_module_schema(m) for m in qs[offset:offset + page_size]]
        return PaginatedAdminModulesSchema(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def create_module(self, data: CreateAdminModuleSchema) -> Optional[AdminModuleSchema]:
        if not AdminSection.objects.filter(id=data.section_id).exists():
            return None
        _ensure_unique_admin_module_code(data.code)
        try:
            module = AdminModule.objects.create(
                code=data.code,
                name=data.name,
                description=data.description or '',
                icon=data.icon,
                route=data.route,
                section_id=data.section_id,
                order=data.order or next_order(AdminModule, section_id=data.section_id),
                is_sidebar=data.is_sidebar,
                is_active=True,
            )
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.MODULE_DUPLICATE_CODE,
                override_detail=f"A module with code '{data.code}' already exists.",
            )
        return _module_schema(AdminModule.objects.select_related('section').get(id=module.id))

    def update_module(self, module_id: uuid.UUID, data: UpdateAdminModuleSchema) -> Optional[AdminModuleSchema]:
        try:
            module = AdminModule.objects.select_related('section').get(id=module_id)
        except AdminModule.DoesNotExist:
            return None
        payload = data.model_dump(exclude_none=True)
        if 'section_id' in payload and not AdminSection.objects.filter(id=payload['section_id']).exists():
            return None
        for field, value in payload.items():
            setattr(module, field, value)
        try:
            module.save()
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.MODULE_DUPLICATE_CODE,
                override_detail=f"A module with code '{module.code}' already exists.",
            )
        return _module_schema(AdminModule.objects.select_related('section').get(id=module_id))

    def toggle_module(self, module_id: uuid.UUID) -> Optional[AdminModuleSchema]:
        try:
            module = AdminModule.objects.select_related('section').get(id=module_id)
        except AdminModule.DoesNotExist:
            return None
        module.is_active = not module.is_active
        module.save(update_fields=['is_active', 'updated_at'])
        return _module_schema(module)

    def delete_module(self, module_id: uuid.UUID) -> bool:
        from django.db import transaction

        from platform.features.security.access.roles.models import AdminRoleModule

        try:
            module = AdminModule.objects.get(id=module_id)
        except AdminModule.DoesNotExist:
            return False
        with transaction.atomic():
            AdminRoleModule.objects.filter(module_code=module.code).delete()
            AdminFeature.objects.filter(module_id=module_id).delete()
            module.delete()
        return True

    def reorder_modules(self, ids: list[uuid.UUID]) -> int:
        return apply_order(AdminModule, ids)

    # ── Features ──────────────────────────────────────────────────────────────

    def list_features_paginated(
        self,
        page: int = 0,
        page_size: int = 10,
        module_code: Optional[str] = None,
        module_id: Optional[uuid.UUID] = None,
        label: Optional[str] = None,
        key: Optional[str] = None,
        category: Optional[str] = None,
    ) -> PaginatedAdminFeaturesSchema:
        from django.db.models.functions import Lower

        qs = AdminFeature.objects.select_related('module').order_by(
            'module__code', category_rank(), Lower('label'), 'key',
        )
        if module_id:
            qs = qs.filter(module_id=module_id)
        elif module_code:
            qs = qs.filter(module__code=module_code)
        if label:
            qs = qs.filter(label__icontains=label.strip())
        if key:
            qs = qs.filter(key__icontains=key.strip())
        if category:
            qs = qs.filter(category=category)
        total = qs.count()
        offset = page * page_size
        items = [_feature_schema(f) for f in qs[offset:offset + page_size]]
        total_pages = (total + page_size - 1) // page_size if page_size else 1
        return PaginatedAdminFeaturesSchema(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(total_pages, 1),
        )

    def create_feature(self, data: CreateAdminFeatureSchema) -> Optional[AdminFeatureSchema]:
        try:
            module = AdminModule.objects.get(code=data.module)
        except AdminModule.DoesNotExist:
            return None
        _ensure_unique_admin_feature_key(data.key)
        try:
            feature = AdminFeature.objects.create(
                module=module,
                key=data.key,
                label=data.label,
                category=data.category or 'features',
                is_active=True,
            )
        except IntegrityError:
            raise ConflictException(
                AppErrorCode.FUNC_DUPLICATE_KEY,
                override_detail=f"A functionality with key '{data.key}' already exists.",
            )
        return _feature_schema(AdminFeature.objects.select_related('module').get(id=feature.id))

    def update_feature(self, feature_id: uuid.UUID, data: UpdateAdminFeatureSchema) -> Optional[AdminFeatureSchema]:
        try:
            feature = AdminFeature.objects.select_related('module').get(id=feature_id)
        except AdminFeature.DoesNotExist:
            return None
        payload = data.model_dump(exclude_none=True)
        if 'module' in payload:
            try:
                feature.module = AdminModule.objects.get(code=payload.pop('module'))
            except AdminModule.DoesNotExist:
                return None
        if 'key' in payload:
            _ensure_unique_admin_feature_key(payload['key'], exclude_id=feature_id)
        for field, value in payload.items():
            setattr(feature, field, value)
        try:
            feature.save()
        except IntegrityError:
            key = payload.get('key', feature.key)
            raise ConflictException(
                AppErrorCode.FUNC_DUPLICATE_KEY,
                override_detail=f"A functionality with key '{key}' already exists.",
            )
        return _feature_schema(AdminFeature.objects.select_related('module').get(id=feature_id))

    def delete_feature(self, feature_id: uuid.UUID) -> bool:
        deleted, _ = AdminFeature.objects.filter(id=feature_id).delete()
        return deleted > 0
