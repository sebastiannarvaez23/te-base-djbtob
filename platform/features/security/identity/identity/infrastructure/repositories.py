import logging
import os
import uuid
from typing import Optional

from core.storage.domain.schemas import UploadFileSchema
from core.storage.infrastructure.minio_storage import MinioStorageService

from platform.features.security.identity.identity.domain.interfaces import (
    IAdminUserPreferencesRepository,
    IAdminUserProfileRepository,
)
from platform.features.security.identity.identity.domain.schemas import (
    AdminUserPreferencesSchema,
    AdminUserProfileSchema,
    UpdateAdminUserPreferencesSchema,
    UpdateAdminUserProfileSchema,
)
from platform.features.security.identity.identity.models import AdminUserPreferences

from ..domain.profile_picture import (
    PROFILE_BUCKET,
    profile_picture_url,
    user_picture_object_key,
)

_logger = logging.getLogger('app.api')

_CONTENT_TYPE_EXT = {
    'image/jpeg': 'jpg',
    'image/png':  'png',
    'image/webp': 'webp',
    'image/gif':  'gif',
}


def _picture_extension(picture) -> str:
    name = getattr(picture, 'name', '') or ''
    ext = os.path.splitext(name)[1].lstrip('.').lower()
    if ext == 'jpeg':
        ext = 'jpg'
    if not ext:
        ext = _CONTENT_TYPE_EXT.get(getattr(picture, 'content_type', ''), 'jpg')
    return ext


def _profile_object_key(username: str, ext: str) -> str:
    return f'admin/users/assets/profiles/pic-{username}.{ext}'


def _to_schema(prefs: AdminUserPreferences) -> AdminUserPreferencesSchema:
    return AdminUserPreferencesSchema(
        id=prefs.id,
        user_id=prefs.user_id,
        language=prefs.language,
        theme=prefs.theme,
        timezone=prefs.timezone,
        date_format=prefs.date_format,
        time_format=prefs.time_format,
        sidebar_collapsed=prefs.sidebar_collapsed,
        items_per_page=prefs.items_per_page,
        notifications_enabled=prefs.notifications_enabled,
        updated_at=prefs.updated_at,
    )


class DjangoAdminUserPreferencesRepository(IAdminUserPreferencesRepository):

    def get_or_create(self, user_id: uuid.UUID) -> AdminUserPreferencesSchema:
        prefs, _ = AdminUserPreferences.objects.get_or_create(user_id=user_id)
        return _to_schema(prefs)

    def update(
        self, user_id: uuid.UUID, data: UpdateAdminUserPreferencesSchema,
    ) -> AdminUserPreferencesSchema:
        prefs, _ = AdminUserPreferences.objects.get_or_create(user_id=user_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(prefs, field, value)
        prefs.save()
        return _to_schema(prefs)


class DjangoAdminUserProfileRepository(IAdminUserProfileRepository):

    def __init__(self, storage=None):
        self._storage = storage or MinioStorageService()

    def _load(self, user_id: uuid.UUID):
        from platform.features.security.identity.users.models import AdminUser
        try:
            return AdminUser.objects.select_related('role').get(id=user_id)
        except AdminUser.DoesNotExist:
            return None

    def _object_key(self, user) -> Optional[str]:
        return user_picture_object_key(user)

    def _public_url(self, object_key: Optional[str]) -> Optional[str]:
        return profile_picture_url(object_key)

    def _to_profile(self, user) -> AdminUserProfileSchema:
        return AdminUserProfileSchema(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            telephone=user.telephone or '',
            picture=self._public_url(self._object_key(user)),
            rol_name=user.role.name if user.role_id else None,
        )

    def get(self, user_id: uuid.UUID) -> Optional[AdminUserProfileSchema]:
        user = self._load(user_id)
        return self._to_profile(user) if user else None

    def update(
        self, user_id: uuid.UUID, data: UpdateAdminUserProfileSchema,
    ) -> Optional[AdminUserProfileSchema]:
        user = self._load(user_id)
        if not user:
            return None

        for field in ('first_name', 'last_name', 'email', 'telephone'):
            value = getattr(data, field)
            if value is not None:
                setattr(user, field, value)

        user.save()
        user.refresh_from_db()
        return self._to_profile(user)

    def set_picture(self, user_id: uuid.UUID, picture) -> Optional[AdminUserProfileSchema]:
        user = self._load(user_id)
        if not user:
            return None

        ext = _picture_extension(picture)
        object_key = _profile_object_key(user.username, ext)

        self._ensure_bucket()

        previous_key = self._object_key(user)
        if previous_key and previous_key != object_key:
            self._safe_delete(previous_key)

        picture.seek(0)
        self._storage.upload_file(UploadFileSchema(
            bucket=PROFILE_BUCKET,
            object_name=object_key,
            data=picture.read(),
            content_type=getattr(picture, 'content_type', None) or 'application/octet-stream',
            metadata={'user_id': str(user.id), 'username': user.username},
        ))

        user.picture = object_key
        user.save(update_fields=['picture'])
        user.refresh_from_db()
        return self._to_profile(user)

    def clear_picture(self, user_id: uuid.UUID) -> Optional[AdminUserProfileSchema]:
        user = self._load(user_id)
        if not user:
            return None

        object_key = self._object_key(user)
        if object_key:
            self._safe_delete(object_key)
            user.picture = None
            user.save(update_fields=['picture'])
            user.refresh_from_db()
        return self._to_profile(user)

    def _ensure_bucket(self) -> None:
        from .profile_storage import ensure_profile_storage

        try:
            ensure_profile_storage(self._storage)
        except Exception as exc:
            _logger.warning('Could not ensure admin profile storage on %s: %s', PROFILE_BUCKET, exc)

    def _safe_delete(self, object_key: str) -> None:
        try:
            self._storage.delete_file(PROFILE_BUCKET, object_key)
        except Exception as exc:
            _logger.warning('Could not delete previous admin profile picture %s: %s', object_key, exc)
