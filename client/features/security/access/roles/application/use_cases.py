from typing import Optional
from uuid import UUID

from client.features.security.access.roles.domain.interfaces import IRoleRepository
from client.features.security.access.roles.domain.schemas import (
    CreateGenericRoleSchema, CreateRoleSchema, RoleSchema, UpdateRoleFeaturesSchema, UpdateRoleSchema,
)
from core.query.core import PaginatedQuery, PaginatedResult
from core.trace import trace_layer


class ListRolesUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: UUID, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_all(company_id, query)


class CreateRoleUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateRoleSchema) -> RoleSchema:
        return self.repository.create(data)


class UpdateRoleUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, role_id: UUID, company_id: UUID, data: UpdateRoleSchema) -> Optional[RoleSchema]:
        return self.repository.update(role_id, company_id, data)


class DeleteRoleUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, role_id: UUID, company_id: UUID) -> bool:
        return self.repository.delete(role_id, company_id)


class ListFeaturesUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery, company_id: UUID | None = None) -> PaginatedResult:
        return self.repository.get_all_features(query, company_id)


class UpdateRoleFeaturesUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, role_id: UUID, company_id: UUID, data: UpdateRoleFeaturesSchema) -> Optional[RoleSchema]:
        return self.repository.update_features(role_id, company_id, data)


class ToggleCompanyRolAccessUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, role_id: UUID, company_id: UUID, is_active: bool) -> Optional[RoleSchema]:
        return self.repository.toggle_company_access(role_id, company_id, is_active)


class ListGenericRolesUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_generic_roles(query)


class CreateGenericRoleUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateGenericRoleSchema) -> RoleSchema:
        return self.repository.create_generic_role(data)


class UpdateGenericRoleUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, role_id: UUID, data: UpdateRoleSchema) -> Optional[RoleSchema]:
        return self.repository.update_generic_role(role_id, data)


class UpdateGenericRoleFeaturesUseCase:
    def __init__(self, repository: IRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, role_id: UUID, data: UpdateRoleFeaturesSchema) -> Optional[RoleSchema]:
        return self.repository.update_generic_role_features(role_id, data)
