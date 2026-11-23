from collections import defaultdict
from typing import Optional
from uuid import UUID

from django.db import transaction
from django.db.models import F, Q
from django.db.models.functions import Lower

from client.features.security.access.roles.domain.interfaces import IRoleRepository
from client.features.security.access.roles.domain.schemas import (
    CreateGenericRoleSchema, CreateRoleSchema, FeatureSchema, RoleSchema, UpdateRoleFeaturesSchema, UpdateRoleSchema,
)
from client.features.security.lifecycle.registration.models import CompanyRolAccess, Rol, RolFeature, RolModule
from core.access.enforcement import ADMIN_ROLE_NAME
from core.errors.codes import AppErrorCode
from core.errors.exceptions import NotFoundException, PermissionException, ValidationAppException
from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.access.functionalities.models import Functionality
from platform.features.security.catalog_order import category_rank


def _licensed_complement_keys(company_id) -> set[str]:
    from platform.features.billing.complement.entitlement.infrastructure.active import (
        active_complement_access,
    )
    keys, _modules = active_complement_access(str(company_id))
    return keys


def _exclude_unassigned_complements(qs, company_id: UUID | None):
    """Complementos fuera del catálogo de roles, salvo los que la empresa ya tiene."""
    if company_id is None:
        return qs.exclude(offering='complement')
    licensed = _licensed_complement_keys(company_id)
    return qs.filter(Q(offering='complement', key__in=licensed) | ~Q(offering='complement'))


def _reject_unlicensed_complements(company_id: UUID, features) -> None:
    complement_keys = {
        feature.key for feature in features if getattr(feature, 'offering', 'plan') == 'complement'
    }
    if not complement_keys:
        return
    missing = complement_keys - _licensed_complement_keys(company_id)
    if missing:
        raise ValidationAppException(AppErrorCode.CMP_NOT_AVAILABLE)


def _paginated(items: list, query: PaginatedQuery) -> PaginatedResult:
    total = len(items)
    if query.unpaginated:
        return PaginatedResult(items=items, total=total, page=0, page_size=0, total_pages=1)
    page_items = items[query.offset: query.offset + query.limit]
    total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
    return PaginatedResult(
        items=page_items, total=total, page=query.page,
        page_size=query.page_size, total_pages=total_pages,
    )


def _load_role_grants(role_ids: list) -> tuple[dict, dict]:
    """Permisos y módulos de varios roles en dos consultas."""
    features: dict = defaultdict(list)
    modules: dict = defaultdict(list)
    if not role_ids:
        return features, modules
    for rol_id, key in RolFeature.objects.filter(
        rol_id__in=role_ids,
        feature__is_active=True,
    ).values_list('rol_id', 'feature__key'):
        features[rol_id].append(key)
    for rol_id, code in RolModule.objects.filter(
        rol_id__in=role_ids,
    ).values_list('rol_id', 'module_code'):
        modules[rol_id].append(code)
    return features, modules


def _company_access_flags(company_id: UUID, role_ids: list) -> dict:
    if not role_ids:
        return {}
    return {
        access.rol_id: access.is_active
        for access in CompanyRolAccess.objects.filter(
            company_id=company_id,
            rol_id__in=role_ids,
        )
    }


def _schema_from_grants(
    rol: Rol,
    *,
    company_id: UUID | None,
    features: list,
    modules: list,
    access_flags: dict,
    complement_keys: set[str],
) -> RoleSchema:
    feature_keys = list(features)
    if company_id is not None and rol.name == ADMIN_ROLE_NAME:
        feature_keys = list(dict.fromkeys([*feature_keys, *complement_keys]))
    is_generic = rol.company_id is None
    if is_generic and company_id is not None:
        is_active = access_flags.get(rol.id, rol.is_active)
    else:
        is_active = rol.is_active
    return RoleSchema(
        id=rol.id,
        name=rol.name,
        description=rol.description,
        is_active=is_active,
        is_generic=is_generic,
        is_editable=not is_generic if company_id is not None else True,
        features=feature_keys,
        modules=list(modules),
    )


def _replace_role_grants(rol: Rol, features, module_codes) -> None:
    RolFeature.objects.filter(rol=rol).delete()
    RolFeature.objects.bulk_create([
        RolFeature(rol=rol, feature=feature)
        for feature in features
    ])
    RolModule.objects.filter(rol=rol).delete()
    if module_codes:
        RolModule.objects.bulk_create([
            RolModule(rol=rol, module_code=code)
            for code in module_codes
        ])


def _to_generic_schema(rol: Rol) -> RoleSchema:
    features = list(
        RolFeature.objects
        .filter(rol=rol, feature__is_active=True)
        .values_list('feature__key', flat=True)
    )
    modules = list(
        RolModule.objects
        .filter(rol=rol)
        .values_list('module_code', flat=True)
    )
    return RoleSchema(
        id=rol.id,
        name=rol.name,
        description=rol.description,
        is_active=rol.is_active,
        is_generic=True,
        is_editable=True,
        features=features,
        modules=modules,
    )


def _to_schema(
    rol: Rol,
    company_id: UUID,
    complement_keys: set[str] | None = None,
) -> RoleSchema:
    features = list(
        RolFeature.objects
        .filter(rol=rol, feature__is_active=True)
        .values_list('feature__key', flat=True)
    )
    if rol.name == ADMIN_ROLE_NAME:
        keys = complement_keys if complement_keys is not None else _licensed_complement_keys(company_id)
        features = list(dict.fromkeys([*features, *keys]))
    modules = list(
        RolModule.objects
        .filter(rol=rol)
        .values_list('module_code', flat=True)
    )
    is_generic = rol.company_id is None
    if is_generic:
        try:
            access = CompanyRolAccess.objects.get(company_id=company_id, rol=rol)
            is_active = access.is_active
        except CompanyRolAccess.DoesNotExist:
            is_active = rol.is_active
    else:
        is_active = rol.is_active

    return RoleSchema(
        id=rol.id,
        name=rol.name,
        description=rol.description,
        is_active=is_active,
        is_generic=is_generic,
        is_editable=not is_generic,
        features=features,
        modules=modules,
    )


class DjangoRoleRepository(IRoleRepository):
    def get_all(self, company_id: UUID, query: PaginatedQuery) -> PaginatedResult:
        qs = Rol.objects.filter(
            Q(company_id=company_id) | Q(company_id__isnull=True)
        ).order_by(F('company_id').asc(nulls_first=True), 'name')
        f = query.filters
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'q' in f:
            qs = qs.filter(Q(name__icontains=f['q']) | Q(description__icontains=f['q']))
        rows = list(qs)
        complement_keys = (
            _licensed_complement_keys(company_id)
            if any(rol.name == ADMIN_ROLE_NAME for rol in rows)
            else set()
        )
        features, modules = _load_role_grants([rol.id for rol in rows])
        access_flags = _company_access_flags(
            company_id,
            [rol.id for rol in rows if rol.company_id is None],
        )
        roles = [
            _schema_from_grants(
                rol,
                company_id=company_id,
                features=features.get(rol.id, []),
                modules=modules.get(rol.id, []),
                access_flags=access_flags,
                complement_keys=complement_keys,
            )
            for rol in rows
        ]
        if 'is_active' in f:
            active = bool(f['is_active'])
            roles = [r for r in roles if r.is_active is active]
        return _paginated(roles, query)

    def create(self, data: CreateRoleSchema) -> RoleSchema:
        rol = Rol.objects.create(name=data.name, description=data.description, company_id=data.company_id)
        return _to_schema(rol, data.company_id)

    def update(self, role_id: UUID, company_id: UUID, data: UpdateRoleSchema) -> Optional[RoleSchema]:
        try:
            rol = Rol.objects.get(id=role_id)
        except Rol.DoesNotExist:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        if rol.company_id is None:
            raise PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        if rol.company_id != company_id:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        if data.name is not None:
            rol.name = data.name
        if data.description is not None:
            rol.description = data.description
        if data.is_active is not None:
            rol.is_active = data.is_active
        rol.save()
        if data.is_active is False:
            from core.access.invalidation import revoke_sessions_for_tenant_role
            revoke_sessions_for_tenant_role(rol.id)
        elif data.is_active is True:
            from core.access.role_cache import RoleFeatureCache
            RoleFeatureCache.invalidate(str(rol.id))
        return _to_schema(rol, company_id)

    def delete(self, role_id: UUID, company_id: UUID) -> bool:
        deleted, _ = Rol.objects.filter(id=role_id, company_id=company_id).delete()
        return deleted > 0

    def get_all_features(self, query: PaginatedQuery, company_id: UUID | None = None) -> PaginatedResult:
        # features → ai → api; within each category alphabetical by label
        qs = Functionality.objects.select_related('module').order_by(
            'module__code', category_rank(), Lower('label'), 'key',
        )
        f = query.filters
        if 'is_active' in f:
            qs = qs.filter(is_active=bool(f['is_active']))
        else:
            qs = qs.filter(is_active=True)
        if 'module' in f:
            qs = qs.filter(module__code=f['module'])
        if 'key' in f:
            qs = qs.filter(key__icontains=f['key'])
        if 'q' in f:
            qs = qs.filter(Q(key__icontains=f['q']) | Q(label__icontains=f['q']))
        qs = _exclude_unassigned_complements(qs, company_id)

        if query.unpaginated:
            items = [
                FeatureSchema(key=row.key, module=row.module.code, label=row.label, category=row.category)
                for row in qs
            ]
            return PaginatedResult(items=items, total=len(items), page=0, page_size=0, total_pages=1)

        total = qs.count()
        items = [
            FeatureSchema(key=row.key, module=row.module.code, label=row.label, category=row.category)
            for row in qs[query.offset: query.offset + query.limit]
        ]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items, total=total, page=query.page,
            page_size=query.page_size, total_pages=total_pages,
        )

    def update_features(self, role_id: UUID, company_id: UUID, data: UpdateRoleFeaturesSchema) -> Optional[RoleSchema]:
        try:
            rol = Rol.objects.get(id=role_id)
        except Rol.DoesNotExist:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        if rol.company_id is None:
            raise PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
        if rol.company_id != company_id:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)

        with transaction.atomic():
            try:
                locked = Rol.objects.select_for_update().get(id=role_id)
            except Rol.DoesNotExist:
                raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
            if locked.company_id is None:
                raise PermissionException(AppErrorCode.ROLE_UNIVERSAL_NOT_EDITABLE)
            if locked.company_id != company_id:
                raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
            valid_features = list(Functionality.objects.filter(key__in=data.feature_keys, is_active=True))
            _reject_unlicensed_complements(company_id, valid_features)
            _replace_role_grants(locked, valid_features, data.module_codes)
            rol = locked

        from core.access.role_cache import RoleFeatureCache
        RoleFeatureCache.invalidate(str(rol.id))
        return _to_schema(rol, company_id)

    # ── Generic roles ─────────────────────────────────────────────────────────

    def get_generic_roles(self, query: PaginatedQuery) -> PaginatedResult:
        qs = Rol.objects.filter(company_id__isnull=True).order_by('name')
        f = query.filters
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'q' in f:
            qs = qs.filter(Q(name__icontains=f['q']) | Q(description__icontains=f['q']))
        if 'is_active' in f:
            qs = qs.filter(is_active=bool(f['is_active']))
        rows = list(qs)
        features, modules = _load_role_grants([rol.id for rol in rows])
        roles = [
            _schema_from_grants(
                rol,
                company_id=None,
                features=features.get(rol.id, []),
                modules=modules.get(rol.id, []),
                access_flags={},
                complement_keys=set(),
            )
            for rol in rows
        ]
        return _paginated(roles, query)

    def create_generic_role(self, data: CreateGenericRoleSchema) -> RoleSchema:
        rol = Rol.objects.create(name=data.name, description=data.description, company_id=None)
        return _to_generic_schema(rol)

    def update_generic_role(self, role_id: UUID, data: UpdateRoleSchema) -> Optional[RoleSchema]:
        try:
            rol = Rol.objects.get(id=role_id, company_id__isnull=True)
        except Rol.DoesNotExist:
            return None
        before_active = rol.is_active
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(rol, field, value)
        rol.save()
        if before_active and not rol.is_active:
            from core.access.invalidation import revoke_sessions_for_tenant_role
            revoke_sessions_for_tenant_role(rol.id)
        else:
            from core.access.role_cache import RoleFeatureCache
            RoleFeatureCache.invalidate(str(rol.id))
        return _to_generic_schema(rol)

    def update_generic_role_features(self, role_id: UUID, data: UpdateRoleFeaturesSchema) -> Optional[RoleSchema]:
        try:
            rol = Rol.objects.get(id=role_id, company_id__isnull=True)
        except Rol.DoesNotExist:
            return None

        with transaction.atomic():
            try:
                locked = Rol.objects.select_for_update().get(id=role_id, company_id__isnull=True)
            except Rol.DoesNotExist:
                return None
            valid_features = list(Functionality.objects.filter(key__in=data.feature_keys, is_active=True))
            if any(getattr(feature, 'offering', 'plan') == 'complement' for feature in valid_features):
                raise ValidationAppException(
                    AppErrorCode.CMP_NOT_AVAILABLE,
                    override_detail='Complement functionalities are granted to the company and cannot be assigned on a shared role.',
                )
            _replace_role_grants(locked, valid_features, data.module_codes)
            rol = locked

        from core.access.role_cache import RoleFeatureCache
        RoleFeatureCache.invalidate(str(rol.id))
        return _to_generic_schema(rol)

    def toggle_company_access(self, role_id: UUID, company_id: UUID, is_active: bool) -> Optional[RoleSchema]:
        try:
            rol = Rol.objects.get(id=role_id, company_id__isnull=True)
        except Rol.DoesNotExist:
            return None
        access, _ = CompanyRolAccess.objects.get_or_create(
            company_id=company_id,
            rol=rol,
            defaults={'is_active': is_active},
        )
        access.is_active = is_active
        access.save()
        if not is_active:
            from core.access.invalidation import revoke_sessions_for_tenant_role_in_company
            revoke_sessions_for_tenant_role_in_company(rol.id, company_id)
        return _to_schema(rol, company_id)
