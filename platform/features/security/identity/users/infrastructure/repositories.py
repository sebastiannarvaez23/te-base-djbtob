import uuid
from typing import Optional

from django.db.models import Q

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.access.roles.domain.schemas import AdminRoleSchema
from platform.features.security.identity.identity.domain.profile_picture import (
    profile_picture_url,
    user_picture_object_key,
)
from platform.features.security.identity.users.models import AdminUser
from platform.features.security.identity.users.domain.interfaces import IAdminUserRepository
from platform.features.security.identity.users.domain.schemas import (
    AdminUserSchema,
    CreateAdminUserSchema,
    UpdateAdminUserSchema,
)


def _to_schema(user: AdminUser) -> AdminUserSchema:
    role = user.role
    return AdminUserSchema(
        id=user.id,
        username=user.username,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        telephone=user.telephone or '',
        rol=AdminRoleSchema(
            id=role.id,
            name=role.name,
            description=role.description,
            is_active=role.is_active,
            created_at=role.created_at,
            updated_at=role.updated_at,
        ),
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        picture=profile_picture_url(user_picture_object_key(user)),
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


class DjangoAdminUserRepository(IAdminUserRepository):

    def _qs(self):
        return AdminUser.objects.select_related('role')

    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        qs = self._qs()
        f = query.filters

        if 'name' in f:
            qs = qs.filter(
                Q(first_name__icontains=f['name']) | Q(last_name__icontains=f['name']),
            )
        if 'email' in f:
            qs = qs.filter(email__icontains=f['email'])
        if 'username' in f:
            qs = qs.filter(username__icontains=f['username'])
        if 'role' in f:
            qs = qs.filter(role__name__icontains=f['role'])
        if 'status' in f:
            qs = qs.filter(is_active=(f['status'] == 'active'))

        qs = qs.order_by('first_name', 'last_name')
        total = qs.count()
        items = [_to_schema(u) for u in qs[query.offset: query.offset + query.limit]]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
        )

    def get_by_id(self, user_id: uuid.UUID) -> Optional[AdminUserSchema]:
        try:
            return _to_schema(self._qs().get(id=user_id))
        except AdminUser.DoesNotExist:
            return None

    def create(self, data: CreateAdminUserSchema) -> AdminUserSchema:
        from django.utils import timezone
        from platform.features.security.auth.auth.application.password_policy import (
            rotate_password,
        )

        user = AdminUser(
            username=data.username,
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            telephone=data.telephone or '',
            role_id=data.rol_id,
            is_superuser=data.is_superuser,
        )
        rotate_password(user, data.password, save=False)
        if user.password_changed_at is None:
            user.password_changed_at = timezone.now()
        user.save()
        return _to_schema(self._qs().get(id=user.id))

    def update(self, user_id: uuid.UUID, data: UpdateAdminUserSchema) -> Optional[AdminUserSchema]:
        from platform.features.security.auth.auth.application.password_policy import (
            rotate_password,
        )

        try:
            user = self._qs().get(id=user_id)
        except AdminUser.DoesNotExist:
            return None
        update_data = data.model_dump(exclude_none=True)
        if 'password' in update_data:
            rotate_password(user, update_data.pop('password'), save=False)
        if 'rol_id' in update_data:
            user.role_id = update_data.pop('rol_id')
        for field, value in update_data.items():
            setattr(user, field, value)
        user.save()
        return _to_schema(self._qs().get(id=user_id))

    def toggle_active(self, user_id: uuid.UUID) -> Optional[AdminUserSchema]:
        try:
            user = self._qs().get(id=user_id)
        except AdminUser.DoesNotExist:
            return None
        user.is_active = not user.is_active
        user.save(update_fields=['is_active', 'updated_at'])
        return _to_schema(user)
