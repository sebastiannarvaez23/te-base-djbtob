import uuid
from typing import List

from core.cache import invalidate_cache, use_case_cache
from core.errors import AppErrorCode, ConflictException, NotFoundException
from core.trace import trace_layer

from platform.features.configuration.admin_parameters.admin_parameter.domain.interfaces import (
    IAdminParameterRepository,
)

from ..domain.interfaces import IAdminParameterTypeRepository
from ..domain.schemas import (
    AdminParameterTypeSchema,
    CreateAdminParameterTypeSchema,
    UpdateAdminParameterTypeSchema,
)

_CACHE_PREFIX = 'admin_parameter_types'


class GetAllAdminParameterTypesUseCase:
    def __init__(self, repository: IAdminParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=_CACHE_PREFIX)
    def execute(self, filters: dict | None = None) -> List[AdminParameterTypeSchema]:
        return self.repository.get_all(filters=filters)


class GetAdminParameterTypeByIdUseCase:
    def __init__(self, repository: IAdminParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=_CACHE_PREFIX)
    def execute(self, id: uuid.UUID) -> AdminParameterTypeSchema:
        result = self.repository.get_by_id(id)
        if not result:
            raise NotFoundException(AppErrorCode.APTYPE_NOT_FOUND)
        return result


class CreateAdminParameterTypeUseCase:
    def __init__(self, repository: IAdminParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateAdminParameterTypeSchema) -> AdminParameterTypeSchema:
        existing = self.repository.get_by_code(data.code)
        if existing:
            raise ConflictException(
                AppErrorCode.APTYPE_DUPLICATE_CODE,
                override_detail=(
                    f"An admin parameter type with code '{data.code}' already exists."
                ),
            )
        result = self.repository.create(data)
        invalidate_cache(f'{_CACHE_PREFIX}:*')
        return result


class UpdateAdminParameterTypeUseCase:
    def __init__(self, repository: IAdminParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, id: uuid.UUID, data: UpdateAdminParameterTypeSchema,
    ) -> AdminParameterTypeSchema:
        if data.code is not None:
            existing = self.repository.get_by_code(data.code)
            if existing and existing.id != id:
                raise ConflictException(
                    AppErrorCode.APTYPE_DUPLICATE_CODE,
                    override_detail=(
                        f"An admin parameter type with code '{data.code}' already exists."
                    ),
                )
        result = self.repository.update(id, data)
        if not result:
            raise NotFoundException(AppErrorCode.APTYPE_NOT_FOUND)
        invalidate_cache(f'{_CACHE_PREFIX}:*')
        return result


class DeleteAdminParameterTypeUseCase:
    def __init__(
        self,
        repository: IAdminParameterTypeRepository,
        parameter_repository: IAdminParameterRepository,
    ):
        self.repository = repository
        self.parameter_repository = parameter_repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        existing = self.repository.get_by_id(id)
        if not existing:
            raise NotFoundException(AppErrorCode.APTYPE_NOT_FOUND)
        if self.parameter_repository.count_by_type(id) > 0:
            raise ConflictException(AppErrorCode.APTYPE_IN_USE)
        deleted = self.repository.delete(id)
        if not deleted:
            raise NotFoundException(AppErrorCode.APTYPE_NOT_FOUND)
        invalidate_cache(f'{_CACHE_PREFIX}:*')
        return deleted
