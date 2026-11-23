import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from platform.features.security.access.roles.domain.schemas import (
    AdminModuleSchema,
    AdminRoleSchema,
    CreateAdminRoleSchema,
    FeatureCatalogItemSchema,
    UpdateAdminRoleFeaturesSchema,
    UpdateAdminRoleSchema,
)


class IAdminRoleRepository(ABC):

    @abstractmethod
    def get_all(self, filters: dict | None = None) -> List[AdminRoleSchema]: ...

    @abstractmethod
    def get_by_id(self, role_id: uuid.UUID) -> Optional[AdminRoleSchema]: ...

    @abstractmethod
    def create(self, data: CreateAdminRoleSchema) -> AdminRoleSchema: ...

    @abstractmethod
    def update(self, role_id: uuid.UUID, data: UpdateAdminRoleSchema) -> Optional[AdminRoleSchema]: ...

    @abstractmethod
    def delete(self, role_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def get_all_modules(self, filters: dict | None = None) -> List[AdminModuleSchema]: ...

    @abstractmethod
    def get_all_features(self, filters: dict | None = None) -> List[FeatureCatalogItemSchema]: ...

    @abstractmethod
    def update_features(
        self,
        role_id: uuid.UUID,
        data: UpdateAdminRoleFeaturesSchema,
    ) -> Optional[AdminRoleSchema]: ...
