import uuid
from abc import ABC, abstractmethod

from platform.features.security.identity.identity.domain.schemas import (
    AdminUserPreferencesSchema,
    AdminUserProfileSchema,
    UpdateAdminUserPreferencesSchema,
    UpdateAdminUserProfileSchema,
)


class IAdminUserPreferencesRepository(ABC):

    @abstractmethod
    def get_or_create(self, user_id: uuid.UUID) -> AdminUserPreferencesSchema: ...

    @abstractmethod
    def update(
        self, user_id: uuid.UUID, data: UpdateAdminUserPreferencesSchema,
    ) -> AdminUserPreferencesSchema: ...


class IAdminUserProfileRepository(ABC):

    @abstractmethod
    def get(self, user_id: uuid.UUID) -> AdminUserProfileSchema | None: ...

    @abstractmethod
    def update(
        self, user_id: uuid.UUID, data: UpdateAdminUserProfileSchema,
    ) -> AdminUserProfileSchema | None: ...

    @abstractmethod
    def set_picture(self, user_id: uuid.UUID, picture) -> AdminUserProfileSchema | None: ...

    @abstractmethod
    def clear_picture(self, user_id: uuid.UUID) -> AdminUserProfileSchema | None: ...
