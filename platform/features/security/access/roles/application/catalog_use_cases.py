import uuid
from typing import List, Optional

from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from platform.features.security.access.roles.domain.catalog_interfaces import IAdminCatalogRepository
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
from core.trace import trace_layer


class ListAdminSectionsUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[AdminSectionSchema]:
        return self.repository.list_sections(filters=filters)


class CreateAdminSectionUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateAdminSectionSchema) -> AdminSectionSchema:
        return self.repository.create_section(data)


class UpdateAdminSectionUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, section_id: uuid.UUID, data: UpdateAdminSectionSchema) -> AdminSectionSchema:
        section = self.repository.update_section(section_id, data)
        if section is None:
            raise NotFoundException(AppErrorCode.SECTION_NOT_FOUND)
        return section


class ToggleAdminSectionUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, section_id: uuid.UUID) -> AdminSectionSchema:
        section = self.repository.toggle_section(section_id)
        if section is None:
            raise NotFoundException(AppErrorCode.SECTION_NOT_FOUND)
        return section


class DeleteAdminSectionUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, section_id: uuid.UUID) -> None:
        if not self.repository.delete_section(section_id):
            raise NotFoundException(AppErrorCode.SECTION_NOT_FOUND)


class ReorderAdminSectionsUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, ids: list[uuid.UUID]) -> int:
        return self.repository.reorder_sections(ids)


class ListAdminCatalogModulesUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, page: int = 0, page_size: int = 200) -> PaginatedAdminModulesSchema:
        return self.repository.list_modules(page=page, page_size=page_size)


class CreateAdminCatalogModuleUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateAdminModuleSchema) -> AdminModuleSchema:
        module = self.repository.create_module(data)
        if module is None:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR, override_detail='Invalid section_id.')
        return module


class UpdateAdminCatalogModuleUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, module_id: uuid.UUID, data: UpdateAdminModuleSchema) -> AdminModuleSchema:
        module = self.repository.update_module(module_id, data)
        if module is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND)
        return module


class ToggleAdminCatalogModuleUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, module_id: uuid.UUID) -> AdminModuleSchema:
        module = self.repository.toggle_module(module_id)
        if module is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND)
        return module


class DeleteAdminCatalogModuleUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, module_id: uuid.UUID) -> None:
        if not self.repository.delete_module(module_id):
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND)


class ReorderAdminCatalogModulesUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, ids: list[uuid.UUID]) -> int:
        return self.repository.reorder_modules(ids)


class ListAdminCatalogFeaturesUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        page: int = 0,
        page_size: int = 10,
        module_code: Optional[str] = None,
        module_id: Optional[uuid.UUID] = None,
        label: Optional[str] = None,
        key: Optional[str] = None,
        category: Optional[str] = None,
    ) -> PaginatedAdminFeaturesSchema:
        return self.repository.list_features_paginated(
            page=page,
            page_size=page_size,
            module_code=module_code,
            module_id=module_id,
            label=label,
            key=key,
            category=category,
        )


class CreateAdminCatalogFeatureUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateAdminFeatureSchema) -> AdminFeatureSchema:
        feature = self.repository.create_feature(data)
        if feature is None:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR, override_detail='Invalid module code.')
        return feature


class UpdateAdminCatalogFeatureUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, feature_id: uuid.UUID, data: UpdateAdminFeatureSchema) -> AdminFeatureSchema:
        feature = self.repository.update_feature(feature_id, data)
        if feature is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Feature not found.')
        return feature


class DeleteAdminCatalogFeatureUseCase:
    def __init__(self, repository: IAdminCatalogRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, feature_id: uuid.UUID) -> None:
        if not self.repository.delete_feature(feature_id):
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Feature not found.')
