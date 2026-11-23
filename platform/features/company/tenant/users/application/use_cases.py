from typing import Optional
from uuid import UUID

from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.company.tenant.users.domain.interfaces import ITenantUserRepository
from platform.features.company.tenant.users.domain.schemas import TenantUserSchema
from core.trace import trace_layer


class ListTenantUsersPaginatedUseCase:
    def __init__(self, repository: ITenantUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_paginated(query)


class ToggleTenantUserActiveUseCase:
    def __init__(self, repository: ITenantUserRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, user_id: UUID) -> Optional[TenantUserSchema]:
        return self.repository.toggle_active(user_id)
