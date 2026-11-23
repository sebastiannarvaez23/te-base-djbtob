import uuid
from typing import List, Optional

from platform.features.security.access.roles.models import (
    AdminFeature,
    AdminModule,
    AdminRole,
    AdminRoleFeature,
    AdminRoleModule,
)
from platform.features.security.access.roles.domain.interfaces import IAdminRoleRepository
from platform.features.security.access.roles.domain.schemas import (
    AdminModuleSchema,
    AdminRoleSchema,
    CreateAdminRoleSchema,
    FeatureCatalogItemSchema,
    UpdateAdminRoleFeaturesSchema,
    UpdateAdminRoleSchema,
)


def _to_schema(role: AdminRole) -> AdminRoleSchema:
    features = list(
        AdminRoleFeature.objects
        .filter(rol=role, feature__is_active=True)
        .values_list('feature__key', flat=True)
    )
    modules = list(
        AdminRoleModule.objects
        .filter(rol=role)
        .values_list('module_code', flat=True)
    )
    return AdminRoleSchema(
        id=role.id,
        name=role.name,
        description=role.description,
        is_active=role.is_active,
        is_generic=False,
        is_editable=True,
        features=features,
        modules=modules,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _to_module_schema(module: AdminModule) -> AdminModuleSchema:
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
        is_active=module.is_active,
        created_at=module.created_at,
        updated_at=module.updated_at,
    )


class DjangoAdminRoleRepository(IAdminRoleRepository):

    def get_all(self, filters: dict | None = None) -> List[AdminRoleSchema]:
        from django.db.models import Q

        qs = AdminRole.objects.all().order_by('name')
        f = filters or {}
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'q' in f:
            qs = qs.filter(Q(name__icontains=f['q']))
        return [_to_schema(r) for r in qs]

    def get_by_id(self, role_id: uuid.UUID) -> Optional[AdminRoleSchema]:
        try:
            return _to_schema(AdminRole.objects.get(id=role_id))
        except AdminRole.DoesNotExist:
            return None

    def create(self, data: CreateAdminRoleSchema) -> AdminRoleSchema:
        role = AdminRole.objects.create(**data.model_dump())
        return _to_schema(role)

    def update(self, role_id: uuid.UUID, data: UpdateAdminRoleSchema) -> Optional[AdminRoleSchema]:
        try:
            role = AdminRole.objects.get(id=role_id)
        except AdminRole.DoesNotExist:
            return None
        before_active = role.is_active
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(role, field, value)
        role.save()
        if before_active and not role.is_active:
            from core.access.invalidation import revoke_sessions_for_admin_role
            revoke_sessions_for_admin_role(role.id)
        return _to_schema(role)

    def delete(self, role_id: uuid.UUID) -> bool:
        deleted, _ = AdminRole.objects.filter(id=role_id).delete()
        return deleted > 0

    def get_all_modules(self, filters: dict | None = None) -> List[AdminModuleSchema]:
        from django.db.models import Q

        qs = AdminModule.objects.select_related('section').order_by('section__order', 'order')
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        else:
            qs = qs.filter(is_active=True)
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        return [_to_module_schema(m) for m in qs]

    def get_all_features(self, filters: dict | None = None) -> List[FeatureCatalogItemSchema]:
        from django.db.models import Q

        from django.db.models.functions import Lower

        from platform.features.security.catalog_order import category_rank

        # features → ai → api; within each category alphabetical by label
        qs = AdminFeature.objects.select_related('module').order_by(
            'module__code', category_rank(), Lower('label'), 'key',
        )
        f = filters or {}
        if 'key' in f:
            qs = qs.filter(key__icontains=f['key'])
        if 'name' in f:
            qs = qs.filter(label__icontains=f['name'])
        if 'module' in f:
            qs = qs.filter(module__code=f['module'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        else:
            qs = qs.filter(is_active=True)
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(key__icontains=q) | Q(label__icontains=q))
        return [
            FeatureCatalogItemSchema(
                key=feat.key,
                module=feat.module.code,
                label=feat.label,
                category=feat.category,
            )
            for feat in qs
        ]

    def update_features(
        self,
        role_id: uuid.UUID,
        data: UpdateAdminRoleFeaturesSchema,
    ) -> Optional[AdminRoleSchema]:
        try:
            role = AdminRole.objects.get(id=role_id)
        except AdminRole.DoesNotExist:
            return None

        valid_features = AdminFeature.objects.filter(key__in=data.feature_keys, is_active=True)
        AdminRoleFeature.objects.filter(rol=role).delete()
        AdminRoleFeature.objects.bulk_create([
            AdminRoleFeature(rol=role, feature=feature)
            for feature in valid_features
        ])

        AdminRoleModule.objects.filter(rol=role).delete()
        if data.module_codes:
            valid_codes = set(
                AdminModule.objects.filter(code__in=data.module_codes, is_active=True)
                .values_list('code', flat=True)
            )
            AdminRoleModule.objects.bulk_create([
                AdminRoleModule(rol=role, module_code=code)
                for code in data.module_codes
                if code in valid_codes
            ])

        return _to_schema(role)
