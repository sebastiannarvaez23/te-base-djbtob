import uuid

from platform.features.security.identity.identity.domain.interfaces import IAdminUserPreferencesRepository
from platform.features.security.identity.identity.domain.schemas import (
    AdminUserPreferencesSchema,
    AdminUserProfileSchema,
    UpdateAdminUserPreferencesSchema,
    UpdateAdminUserProfileSchema,
)
from core.trace import trace_layer


class GetAdminUserPreferencesUseCase:
    def __init__(self, repository: IAdminUserPreferencesRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> AdminUserPreferencesSchema:
        return self.repository.get_or_create(user_id)


class UpdateAdminUserPreferencesUseCase:
    def __init__(self, repository: IAdminUserPreferencesRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, user_id: uuid.UUID, data: UpdateAdminUserPreferencesSchema,
    ) -> AdminUserPreferencesSchema:
        return self.repository.update(user_id, data)


class GetAdminUserProfileUseCase:
    def __init__(self, repository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> AdminUserProfileSchema | None:
        return self.repository.get(user_id)


class UpdateAdminUserProfileUseCase:
    def __init__(self, repository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, user_id: uuid.UUID, data: UpdateAdminUserProfileSchema,
    ) -> AdminUserProfileSchema | None:
        return self.repository.update(user_id, data)


class UpdateAdminUserProfilePictureUseCase:
    def __init__(self, repository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID, picture) -> AdminUserProfileSchema | None:
        return self.repository.set_picture(user_id, picture)


class DeleteAdminUserProfilePictureUseCase:
    def __init__(self, repository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> AdminUserProfileSchema | None:
        return self.repository.clear_picture(user_id)
