import logging
import os
import uuid
from typing import Optional

from django.db import IntegrityError, transaction

from core.errors import AppErrorCode, ConflictException
from core.storage.domain.schemas import UploadFileSchema
from core.storage.infrastructure.minio_storage import MinioStorageService

from ..domain.interfaces import IUserPreferencesRepository, IUserProfileRepository
from ..domain.schemas import (
    UpdateUserPreferencesSchema,
    UpdateUserProfileSchema,
    UserPreferencesSchema,
    UserProfileSchema,
)
from ..models import UserPreferences

_logger = logging.getLogger('app.api')

# Bucket/path constants re-exported for backwards compatibility.
from ..domain.profile_picture import (  # noqa: F401
    DEFAULT_AVATAR_PUBLIC_PATTERN,
    DEFAULT_PROFILE_AVATAR_KEY,
    PROFILE_BUCKET,
    PROFILE_PUBLIC_PATTERN,
    default_profile_picture_url,
    profile_picture_url,
    resolve_profile_picture_url,
    user_picture_object_key,
)

_CONTENT_TYPE_EXT = {
    'image/jpeg': 'jpg',
    'image/png':  'png',
    'image/webp': 'webp',
    'image/gif':  'gif',
}


def _picture_extension(picture) -> str:
    """Resolve a clean file extension from the uploaded file name / content type."""
    name = getattr(picture, 'name', '') or ''
    ext = os.path.splitext(name)[1].lstrip('.').lower()
    if ext == 'jpeg':
        ext = 'jpg'
    if not ext:
        ext = _CONTENT_TYPE_EXT.get(getattr(picture, 'content_type', ''), 'jpg')
    return ext


def _profile_object_key(tenant_code: str, username: str, ext: str) -> str:
    return f'client/tenants/{tenant_code}/assets/profiles/pic-{username}.{ext}'


class DjangoUserPreferencesRepository(IUserPreferencesRepository):

    def get_or_create(self, user_id: uuid.UUID) -> UserPreferencesSchema:
        preferences, _ = UserPreferences.objects.get_or_create(user_id=user_id)
        return UserPreferencesSchema.model_validate(preferences)

    def update(self, user_id: uuid.UUID, data: UpdateUserPreferencesSchema) -> UserPreferencesSchema:
        preferences, _ = UserPreferences.objects.get_or_create(user_id=user_id)
        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(preferences, field, value)
        preferences.save()
        return UserPreferencesSchema.model_validate(preferences)


class DjangoUserProfileRepository(IUserProfileRepository):

    def __init__(self, storage=None):
        self._storage = storage or MinioStorageService()

    def _load(self, user_id: uuid.UUID):
        from client.features.security.lifecycle.registration.models import User
        try:
            return User.objects.select_related('rol', 'company').get(id=user_id)
        except User.DoesNotExist:
            return None

    def _object_key(self, user) -> Optional[str]:
        """The stored MinIO object key for this user's picture (or None)."""
        return user_picture_object_key(user)

    def _public_url(self, object_key: Optional[str]) -> Optional[str]:
        """Permanent (non-expiring) public URL for a profile picture object."""
        return profile_picture_url(object_key)

    def _to_profile(self, user) -> UserProfileSchema:
        return UserProfileSchema(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            second_name=user.second_name or '',
            last_name=user.last_name,
            second_last_name=user.second_last_name or '',
            document_type=user.document_type or '',
            document_number=user.document_number or '',
            email=user.email,
            telephone=user.telephone,
            phone_country_code=user.phone_country_code or 'CO',
            # Permanent public URL; the DB keeps the object key (route).
            picture=self._public_url(self._object_key(user)),
            rol_name=user.rol.name if user.rol_id else None,
            company_name=user.company.name if user.company_id else None,
        )

    def get(self, user_id: uuid.UUID) -> Optional[UserProfileSchema]:
        user = self._load(user_id)
        return self._to_profile(user) if user else None

    def document_taken(
        self,
        user_id: uuid.UUID,
        document_type: str,
        document_number: str,
    ) -> bool:
        if not document_number:
            return False
        user = self._load(user_id)
        if not user:
            return False
        from client.features.security.lifecycle.registration.models import User
        return (
            User.objects
            .filter(
                company_id=user.company_id,
                document_type=document_type or '',
                document_number=document_number,
            )
            .exclude(id=user.id)
            .exists()
        )

    def update(self, user_id: uuid.UUID, data: UpdateUserProfileSchema) -> Optional[UserProfileSchema]:
        user = self._load(user_id)
        if not user:
            return None

        for field in (
            'first_name',
            'second_name',
            'last_name',
            'second_last_name',
            'document_type',
            'document_number',
            'email',
            'telephone',
            'phone_country_code',
        ):
            value = getattr(data, field, None)
            if value is not None:
                if field == 'document_type':
                    value = getattr(value, 'value', value)
                setattr(user, field, value)

        try:
            with transaction.atomic():
                user.save()
        except IntegrityError as exc:
            if 'uniq_user_company_document' in str(exc).lower():
                raise ConflictException(AppErrorCode.USER_DUPLICATE_DOCUMENT) from exc
            raise

        user.refresh_from_db()
        return self._to_profile(user)

    def set_picture(self, user_id: uuid.UUID, picture) -> Optional[UserProfileSchema]:
        user = self._load(user_id)
        if not user:
            return None

        tenant_code = user.company.schema_name
        ext = _picture_extension(picture)
        object_key = _profile_object_key(tenant_code, user.username, ext)

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

        # Persist the MinIO route in the picture field.
        user.picture = object_key
        user.save(update_fields=['picture'])
        user.refresh_from_db()
        return self._to_profile(user)

    def clear_picture(self, user_id: uuid.UUID) -> Optional[UserProfileSchema]:
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

    # ── MinIO helpers ────────────────────────────────────────────────────────

    def _ensure_bucket(self) -> None:
        from .profile_storage import ensure_profile_storage

        try:
            ensure_profile_storage(self._storage)
        except Exception as exc:
            _logger.warning('Could not ensure profile storage on %s: %s', PROFILE_BUCKET, exc)

    def _safe_delete(self, object_key: str) -> None:
        try:
            self._storage.delete_file(PROFILE_BUCKET, object_key)
        except Exception as exc:  # best-effort cleanup; never block the request
            _logger.warning('Could not delete previous profile picture %s: %s', object_key, exc)
