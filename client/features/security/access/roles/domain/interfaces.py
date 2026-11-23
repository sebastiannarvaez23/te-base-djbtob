from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from client.features.security.access.roles.domain.schemas import (
    CreateRoleSchema, CreateGenericRoleSchema, FeatureSchema, RoleSchema, UpdateRoleFeaturesSchema, UpdateRoleSchema,
)
from core.query.core import PaginatedQuery, PaginatedResult


class IRoleRepository(ABC):
    @abstractmethod
    def get_all(self, company_id: UUID, query: PaginatedQuery) -> PaginatedResult: ...

    @abstractmethod
    def create(self, data: CreateRoleSchema) -> RoleSchema: ...

    @abstractmethod
    def update(self, role_id: UUID, company_id: UUID, data: UpdateRoleSchema) -> Optional[RoleSchema]: ...

    @abstractmethod
    def delete(self, role_id: UUID, company_id: UUID) -> bool: ...

    @abstractmethod
    def get_all_features(
        self, query: PaginatedQuery, company_id: UUID | None = None,
    ) -> PaginatedResult: ...

    @abstractmethod
    def update_features(self, role_id: UUID, company_id: UUID, data: UpdateRoleFeaturesSchema) -> Optional[RoleSchema]: ...

    @abstractmethod
    def toggle_company_access(self, role_id: UUID, company_id: UUID, is_active: bool) -> Optional[RoleSchema]: ...

    # ── Generic roles (company_id=None) ───────────────────────────────────────

    @abstractmethod
    def get_generic_roles(self, query: PaginatedQuery) -> PaginatedResult: ...

    @abstractmethod
    def create_generic_role(self, data: CreateGenericRoleSchema) -> RoleSchema: ...

    @abstractmethod
    def update_generic_role(self, role_id: UUID, data: UpdateRoleSchema) -> Optional[RoleSchema]: ...

    @abstractmethod
    def update_generic_role_features(self, role_id: UUID, data: UpdateRoleFeaturesSchema) -> Optional[RoleSchema]: ...
