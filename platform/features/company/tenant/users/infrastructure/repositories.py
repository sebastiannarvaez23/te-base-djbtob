from typing import Optional
from uuid import UUID

from django.db.models import Q

from core.query.core import PaginatedQuery, PaginatedResult
from client.features.security.identity.identity.domain.profile_picture import (
    profile_picture_url,
    user_picture_object_key,
)
from client.features.security.lifecycle.registration.models import User
from platform.features.company.tenant.company.domain.lifecycle import (
    DIRECTORY_HIDDEN_LIFECYCLES,
    TOMBSTONE_EMAIL_DOMAIN,
)
from platform.features.company.tenant.users.domain.interfaces import ITenantUserRepository
from platform.features.company.tenant.users.domain.schemas import TenantUserSchema, TenantUserRolSchema


def _to_schema(user: User) -> TenantUserSchema:
    rol = None
    if user.rol_id:
        rol = TenantUserRolSchema(id=user.rol.id, name=user.rol.name)
    return TenantUserSchema(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        username=user.username,
        telephone=user.telephone,
        company_name=user.company.name,
        company_nit=user.company.nit,
        rol=rol,
        is_active=user.is_active,
        picture=profile_picture_url(user_picture_object_key(user)),
    )


class DjangoTenantUserRepository(ITenantUserRepository):

    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        qs = (
            User.objects
            .select_related('rol', 'company')
            .exclude(company__lifecycle__in=DIRECTORY_HIDDEN_LIFECYCLES)
            .exclude(email__iendswith=f'@{TOMBSTONE_EMAIL_DOMAIN}')
        )
        f = query.filters

        if 'name' in f:
            qs = qs.filter(
                Q(first_name__icontains=f['name']) | Q(last_name__icontains=f['name']),
            )
        if 'email' in f:
            qs = qs.filter(email__icontains=f['email'])
        if 'company' in f:
            qs = qs.filter(company__name__icontains=f['company'])
        if 'status' in f:
            qs = qs.filter(is_active=(f['status'] == 'active'))

        qs = qs.order_by('first_name', 'last_name')
        total = qs.count()
        items = [_to_schema(u) for u in qs[query.offset: query.offset + query.limit]]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(items=items, total=total, page=query.page, page_size=query.page_size, total_pages=total_pages)

    def toggle_active(self, user_id: UUID) -> Optional[TenantUserSchema]:
        try:
            user = (
                User.objects
                .select_related('rol', 'company')
                .exclude(company__lifecycle__in=DIRECTORY_HIDDEN_LIFECYCLES)
                .exclude(email__iendswith=f'@{TOMBSTONE_EMAIL_DOMAIN}')
                .get(id=user_id)
            )
        except User.DoesNotExist:
            return None
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        return _to_schema(user)
