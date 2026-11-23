import uuid
from typing import List, Optional

from platform.features.security.access.roles.domain.interfaces import IAdminRoleRepository
from platform.features.security.access.roles.domain.schemas import (
    AdminModuleSchema,
    AdminRoleSchema,
    CreateAdminRoleSchema,
    FeatureCatalogItemSchema,
    UpdateAdminRoleFeaturesSchema,
    UpdateAdminRoleSchema,
)
from core.trace import trace_layer


class ListAdminRolesUseCase:
    def __init__(self, repository: IAdminRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[AdminRoleSchema]:
        return self.repository.get_all(filters=filters)


class CreateAdminRoleUseCase:
    def __init__(self, repository: IAdminRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateAdminRoleSchema) -> AdminRoleSchema:
        return self.repository.create(data)


class UpdateAdminRoleUseCase:
    def __init__(self, repository: IAdminRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, role_id: uuid.UUID, data: UpdateAdminRoleSchema) -> Optional[AdminRoleSchema]:
        return self.repository.update(role_id, data)


class DeleteAdminRoleUseCase:
    def __init__(self, repository: IAdminRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, role_id: uuid.UUID) -> bool:
        return self.repository.delete(role_id)


class ListAdminModulesUseCase:
    def __init__(self, repository: IAdminRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[AdminModuleSchema]:
        return self.repository.get_all_modules(filters=filters)


class ListAdminFeaturesUseCase:
    def __init__(self, repository: IAdminRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[FeatureCatalogItemSchema]:
        return self.repository.get_all_features(filters=filters)


class UpdateAdminRoleFeaturesUseCase:
    def __init__(self, repository: IAdminRoleRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        role_id: uuid.UUID,
        data: UpdateAdminRoleFeaturesSchema,
    ) -> Optional[AdminRoleSchema]:
        return self.repository.update_features(role_id, data)
