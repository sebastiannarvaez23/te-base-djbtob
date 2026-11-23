import uuid
from abc import ABC, abstractmethod
from typing import Optional

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.identity.users.domain.schemas import (
    AdminUserSchema,
    CreateAdminUserSchema,
    UpdateAdminUserSchema,
)


class IAdminUserRepository(ABC):

    @abstractmethod
    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult: ...

    @abstractmethod
    def get_by_id(self, user_id: uuid.UUID) -> Optional[AdminUserSchema]: ...

    @abstractmethod
    def create(self, data: CreateAdminUserSchema) -> AdminUserSchema: ...

    @abstractmethod
    def update(self, user_id: uuid.UUID, data: UpdateAdminUserSchema) -> Optional[AdminUserSchema]: ...

    @abstractmethod
    def toggle_active(self, user_id: uuid.UUID) -> Optional[AdminUserSchema]: ...
