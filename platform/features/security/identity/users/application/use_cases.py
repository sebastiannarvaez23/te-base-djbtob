import uuid
from typing import Optional

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.identity.users.domain.interfaces import IAdminUserRepository
from platform.features.security.identity.users.domain.schemas import (
    AdminUserSchema,
    CreateAdminUserSchema,
    UpdateAdminUserSchema,
)
from core.trace import trace_layer


class ListAdminUsersPaginatedUseCase:
    def __init__(self, repository: IAdminUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_paginated(query)


class GetAdminUserUseCase:
    def __init__(self, repository: IAdminUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> Optional[AdminUserSchema]:
        return self.repository.get_by_id(user_id)


class CreateAdminUserUseCase:
    def __init__(self, repository: IAdminUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateAdminUserSchema) -> AdminUserSchema:
        return self.repository.create(data)


class UpdateAdminUserUseCase:
    def __init__(self, repository: IAdminUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID, data: UpdateAdminUserSchema) -> Optional[AdminUserSchema]:
        return self.repository.update(user_id, data)


class ToggleAdminUserActiveUseCase:
    def __init__(self, repository: IAdminUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: uuid.UUID) -> Optional[AdminUserSchema]:
        return self.repository.toggle_active(user_id)
