import uuid
from typing import List, Optional

from core.errors import NotFoundException, ConflictException, AppErrorCode
from ..domain.interfaces import IParameterTypeRepository
from ..domain.schemas import (
    CreateParameterTypeSchema,
    ParameterTypeSchema,
    UpdateParameterTypeSchema,
)
from core.trace import trace_layer


class GetAllParameterTypesUseCase:
    def __init__(self, repository: IParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[ParameterTypeSchema]:
        return self.repository.get_all(filters=filters)


class GetParameterTypeByIdUseCase:
    def __init__(self, repository: IParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> ParameterTypeSchema:
        result = self.repository.get_by_id(id)
        if not result:
            raise NotFoundException(AppErrorCode.PTYPE_NOT_FOUND)
        return result


class CreateParameterTypeUseCase:
    def __init__(self, repository: IParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateParameterTypeSchema) -> ParameterTypeSchema:
        existing = self.repository.get_by_code(data.code)
        if existing:
            raise ConflictException(
                AppErrorCode.PTYPE_DUPLICATE_CODE,
                override_detail=f"A parameter type with code '{data.code}' already exists.",
            )
        return self.repository.create(data)


class UpdateParameterTypeUseCase:
    def __init__(self, repository: IParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdateParameterTypeSchema) -> ParameterTypeSchema:
        if data.code is not None:
            existing = self.repository.get_by_code(data.code)
            if existing and existing.id != id:
                raise ConflictException(
                    AppErrorCode.PTYPE_DUPLICATE_CODE,
                    override_detail=f"A parameter type with code '{data.code}' already exists.",
                )
        result = self.repository.update(id, data)
        if not result:
            raise NotFoundException(AppErrorCode.PTYPE_NOT_FOUND)
        return result


class DeleteParameterTypeUseCase:
    def __init__(self, repository: IParameterTypeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        deleted = self.repository.delete(id)
        if not deleted:
            raise NotFoundException(AppErrorCode.PTYPE_NOT_FOUND)
        return deleted
