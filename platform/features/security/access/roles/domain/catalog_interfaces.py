import uuid
from abc import ABC, abstractmethod
from typing import List, Optional

from platform.features.security.access.roles.domain.catalog_schemas import (
    AdminFeatureSchema,
    AdminModuleSchema,
    AdminSectionSchema,
    CreateAdminFeatureSchema,
    CreateAdminModuleSchema,
    CreateAdminSectionSchema,
    PaginatedAdminFeaturesSchema,
    PaginatedAdminModulesSchema,
    UpdateAdminFeatureSchema,
    UpdateAdminModuleSchema,
    UpdateAdminSectionSchema,
)


class IAdminCatalogRepository(ABC):

    @abstractmethod
    def list_sections(self, filters: dict | None = None) -> List[AdminSectionSchema]: ...

    @abstractmethod
    def create_section(self, data: CreateAdminSectionSchema) -> AdminSectionSchema: ...

    @abstractmethod
    def update_section(self, section_id: uuid.UUID, data: UpdateAdminSectionSchema) -> Optional[AdminSectionSchema]: ...

    @abstractmethod
    def toggle_section(self, section_id: uuid.UUID) -> Optional[AdminSectionSchema]: ...

    @abstractmethod
    def delete_section(self, section_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def reorder_sections(self, ids: list[uuid.UUID]) -> int: ...

    @abstractmethod
    def list_modules(self, page: int = 0, page_size: int = 200) -> PaginatedAdminModulesSchema: ...

    @abstractmethod
    def create_module(self, data: CreateAdminModuleSchema) -> Optional[AdminModuleSchema]: ...

    @abstractmethod
    def update_module(self, module_id: uuid.UUID, data: UpdateAdminModuleSchema) -> Optional[AdminModuleSchema]: ...

    @abstractmethod
    def toggle_module(self, module_id: uuid.UUID) -> Optional[AdminModuleSchema]: ...

    @abstractmethod
    def delete_module(self, module_id: uuid.UUID) -> bool: ...

    @abstractmethod
    def reorder_modules(self, ids: list[uuid.UUID]) -> int: ...

    @abstractmethod
    def list_features_paginated(
        self,
        page: int = 0,
        page_size: int = 10,
        module_code: Optional[str] = None,
        module_id: Optional[uuid.UUID] = None,
        label: Optional[str] = None,
        key: Optional[str] = None,
        category: Optional[str] = None,
    ) -> PaginatedAdminFeaturesSchema: ...

    @abstractmethod
    def create_feature(self, data: CreateAdminFeatureSchema) -> Optional[AdminFeatureSchema]: ...

    @abstractmethod
    def update_feature(self, feature_id: uuid.UUID, data: UpdateAdminFeatureSchema) -> Optional[AdminFeatureSchema]: ...

    @abstractmethod
    def delete_feature(self, feature_id: uuid.UUID) -> bool: ...
