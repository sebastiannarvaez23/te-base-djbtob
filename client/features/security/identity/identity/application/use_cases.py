import uuid
from typing import Optional

from core.errors import AppErrorCode, ConflictException, ValidationAppException
from client.features.security.lifecycle.registration.domain.identity import (
    IdentityFieldError,
    assert_identity_invariants,
)

from ..domain.interfaces import IUserPreferencesRepository, IUserProfileRepository
from ..domain.schemas import (
    UpdateUserPreferencesSchema,
    UpdateUserProfileSchema,
    UserPreferencesSchema,
    UserProfileSchema,
)
from core.trace import trace_layer


def _document_type_code(value) -> str:
    if value is None:
        return ''
    return getattr(value, 'value', None) or str(value)


class GetUserPreferencesUseCase:
    def __init__(self, repository: IUserPreferencesRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> UserPreferencesSchema:
        return self.repository.get_or_create(user_id)


class UpdateUserPreferencesUseCase:
    def __init__(self, repository: IUserPreferencesRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID, data: UpdateUserPreferencesSchema) -> UserPreferencesSchema:
        return self.repository.update(user_id, data)


class GetUserProfileUseCase:
    def __init__(self, repository: IUserProfileRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> Optional[UserProfileSchema]:
        return self.repository.get(user_id)


class UpdateUserProfileUseCase:
    def __init__(self, repository: IUserProfileRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID, data: UpdateUserProfileSchema) -> Optional[UserProfileSchema]:
        current = self.repository.get(user_id)
        if current is None:
            return None

        merged_type = data.document_type if data.document_type is not None else current.document_type
        merged_number = data.document_number if data.document_number is not None else current.document_number
        merged_country = (
            data.phone_country_code if data.phone_country_code is not None
            else current.phone_country_code
        )
        merged_telephone = data.telephone if data.telephone is not None else current.telephone
        try:
            assert_identity_invariants(
                document_type=merged_type,
                document_number=merged_number,
                phone_country_code=merged_country,
                telephone=merged_telephone,
            )
        except IdentityFieldError as exc:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail=str(exc),
            ) from exc

        number = merged_number or ''
        if number and self.repository.document_taken(
            user_id,
            _document_type_code(merged_type),
            number,
        ):
            raise ConflictException(AppErrorCode.USER_DUPLICATE_DOCUMENT)

        return self.repository.update(user_id, data)


class UpdateUserProfilePictureUseCase:
    def __init__(self, repository: IUserProfileRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID, picture) -> Optional[UserProfileSchema]:
        return self.repository.set_picture(user_id, picture)


class DeleteUserProfilePictureUseCase:
    def __init__(self, repository: IUserProfileRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> Optional[UserProfileSchema]:
        return self.repository.clear_picture(user_id)
