import uuid
from abc import ABC, abstractmethod
from typing import Optional

from .schemas import (
    UpdateUserPreferencesSchema,
    UpdateUserProfileSchema,
    UserPreferencesSchema,
    UserProfileSchema,
)


class IUserPreferencesRepository(ABC):

    @abstractmethod
    def get_or_create(self, user_id: uuid.UUID) -> UserPreferencesSchema:
        ...

    @abstractmethod
    def update(self, user_id: uuid.UUID, data: UpdateUserPreferencesSchema) -> UserPreferencesSchema:
        ...


class IUserProfileRepository(ABC):

    @abstractmethod
    def get(self, user_id: uuid.UUID) -> Optional[UserProfileSchema]:
        ...

    @abstractmethod
    def document_taken(
        self,
        user_id: uuid.UUID,
        document_type: str,
        document_number: str,
    ) -> bool:
        ...

    @abstractmethod
    def update(self, user_id: uuid.UUID, data: UpdateUserProfileSchema) -> Optional[UserProfileSchema]:
        ...

    @abstractmethod
    def set_picture(self, user_id: uuid.UUID, picture) -> Optional[UserProfileSchema]:
        ...

    @abstractmethod
    def clear_picture(self, user_id: uuid.UUID) -> Optional[UserProfileSchema]:
        ...
