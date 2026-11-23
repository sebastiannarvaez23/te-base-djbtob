from typing import Optional
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from client.features.security.lifecycle.registration.domain.schemas import RolSchema
from client.features.security.identity.users.domain.interfaces import ICompanyUserRepository
from client.features.security.identity.users.domain.schemas import (
    CompanyUserSchema,
    CreateCompanyUserSchema,
    UpdateCompanyUserSchema,
)
from client.features.security.identity.identity.domain.profile_picture import (
    profile_picture_url,
    user_picture_object_key,
)
from client.features.security.lifecycle.auth.application.password_policy import rotate_password
from client.features.security.lifecycle.registration.models import Rol, User
from core.errors import AppErrorCode, ConflictException
from platform.features.company.tenant.company.domain.lifecycle import TOMBSTONE_EMAIL_DOMAIN


def colleague_search_filter(term: str) -> Q:
    """Match a share-box term against name parts, username, or email."""
    return (
        Q(first_name__icontains=term)
        | Q(second_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(second_last_name__icontains=term)
        | Q(username__icontains=term)
        | Q(email__icontains=term)
    )


def _rol_to_schema(rol: Rol) -> RolSchema:
    return RolSchema(id=rol.id, name=rol.name)


def _document_code(value) -> str:
    if value is None:
        return ''
    return getattr(value, 'value', value) or ''


def _ensure_unique_document(user: User) -> None:
    number = (user.document_number or '').strip()
    if not number:
        return
    taken = (
        User.objects
        .filter(
            company_id=user.company_id,
            document_type=user.document_type or '',
            document_number=number,
        )
        .exclude(pk=user.pk)
        .exists()
    )
    if taken:
        raise ConflictException(AppErrorCode.USER_DUPLICATE_DOCUMENT)


def _save_user(user: User) -> None:
    try:
        with transaction.atomic():
            _ensure_unique_document(user)
            user.save()
    except IntegrityError as exc:
        if 'uniq_user_company_document' in str(exc).lower():
            raise ConflictException(AppErrorCode.USER_DUPLICATE_DOCUMENT) from exc
        raise


def _user_to_schema(user: User) -> CompanyUserSchema:
    return CompanyUserSchema(
        id=user.id,
        first_name=user.first_name,
        second_name=user.second_name or '',
        last_name=user.last_name,
        second_last_name=user.second_last_name or '',
        document_type=user.document_type or '',
        document_number=user.document_number or '',
        birth_date=user.birth_date,
        email=user.email,
        username=user.username,
        telephone=user.telephone,
        rol=_rol_to_schema(user.rol),
        is_active=user.is_active,
        picture=profile_picture_url(user_picture_object_key(user)),
    )


class DjangoCompanyUserRepository(ICompanyUserRepository):
    def list(
        self,
        company_id: UUID,
        filters: dict,
        offset: int,
        limit: int,
    ) -> tuple[list[CompanyUserSchema], int]:
        qs = (
            User.objects
            .filter(company_id=company_id)
            .select_related('rol')
            .exclude(email__iendswith=f'@{TOMBSTONE_EMAIL_DOMAIN}')
        )

        if term := (filters.get('q') or '').strip():
            qs = qs.filter(colleague_search_filter(term))
        if name := filters.get('name'):
            qs = qs.filter(
                Q(first_name__icontains=name)
                | Q(second_name__icontains=name)
                | Q(last_name__icontains=name)
                | Q(second_last_name__icontains=name)
            )
        if email := filters.get('email'):
            qs = qs.filter(email__icontains=email)
        if username := filters.get('username'):
            qs = qs.filter(username__icontains=username)
        if role := filters.get('role'):
            qs = qs.filter(rol__name__icontains=role)
        if status := filters.get('status'):
            qs = qs.filter(is_active=(status == 'active'))

        qs = qs.order_by('first_name', 'last_name')
        total = qs.count()
        items = [_user_to_schema(u) for u in qs[offset:offset + limit]]
        return items, total

    def create(self, data: CreateCompanyUserSchema) -> CompanyUserSchema:
        rol = Rol.objects.get(id=data.rol_id)
        user = User(
            first_name=data.first_name,
            second_name=data.second_name or '',
            last_name=data.last_name,
            second_last_name=data.second_last_name,
            document_type=_document_code(data.document_type),
            document_number=data.document_number,
            birth_date=data.birth_date,
            email=data.email,
            username=data.username,
            telephone=data.telephone,
            company_id=data.company_id,
            rol=rol,
        )
        if data.password:
            rotate_password(user, data.password, save=False)
        else:
            user.set_unusable_password()
        _save_user(user)
        user = User.objects.select_related('rol').get(pk=user.pk)
        return _user_to_schema(user)

    def get_by_id(self, user_id: UUID, company_id: UUID) -> Optional[CompanyUserSchema]:
        try:
            user = User.objects.select_related('rol').get(id=user_id, company_id=company_id)
            return _user_to_schema(user)
        except User.DoesNotExist:
            return None

    def update(
        self,
        user_id: UUID,
        company_id: UUID,
        data: UpdateCompanyUserSchema,
    ) -> Optional[CompanyUserSchema]:
        try:
            user = User.objects.select_related('rol').get(id=user_id, company_id=company_id)
        except User.DoesNotExist:
            return None

        for field in (
            'first_name',
            'second_name',
            'last_name',
            'second_last_name',
            'document_number',
            'email',
            'telephone',
            'birth_date',
        ):
            value = getattr(data, field)
            if value is not None:
                setattr(user, field, value)

        if data.document_type is not None:
            user.document_type = _document_code(data.document_type)

        if data.password is not None:
            rotate_password(user, data.password, save=False)

        if data.rol_id is not None:
            user.rol = Rol.objects.get(id=data.rol_id)

        _save_user(user)
        user.refresh_from_db()
        return _user_to_schema(user)

    def toggle_active(self, user_id: UUID, company_id: UUID) -> Optional[CompanyUserSchema]:
        try:
            user = User.objects.select_related('rol').get(id=user_id, company_id=company_id)
        except User.DoesNotExist:
            return None

        user.is_active = not user.is_active
        user.save()
        return _user_to_schema(user)
