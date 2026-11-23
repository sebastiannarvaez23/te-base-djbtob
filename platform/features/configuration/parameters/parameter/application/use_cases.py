import uuid
from typing import List

from core.auth.inactivity import clear_inactivity_cache
from core.cache import use_case_cache, invalidate_cache
from core.errors import NotFoundException, ConflictException, ValidationAppException, AppErrorCode
from core.parameters import clear_parameter_cache
from core.validators import DataTypeValueValidator
from ..domain.enums import DataType
from ..domain.interfaces import IParameterRepository
from ..domain.schemas import (
    CreateParameterSchema,
    ParameterSchema,
    UpdateParameterSchema,
)
from core.trace import trace_layer

VALID_DATA_TYPES = {dt.value for dt in DataType}
_IDLE_PARAM = 'TIME_INACTIVITY'


def _bump_runtime_caches(*codes: str) -> None:
    for code in codes:
        if not code:
            continue
        clear_parameter_cache(code)
        if code == _IDLE_PARAM:
            clear_inactivity_cache()



class GetAllParametersUseCase:
    def __init__(self, repository: IParameterRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix='parameters')
    def execute(self, filters: dict | None = None) -> List[ParameterSchema]:
        return self.repository.get_all(filters=filters)


class GetParameterByIdUseCase:
    def __init__(self, repository: IParameterRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix='parameters')
    def execute(self, id: uuid.UUID) -> ParameterSchema:
        result = self.repository.get_by_id(id)
        if not result:
            raise NotFoundException(AppErrorCode.PARAM_NOT_FOUND)
        return result


class CreateParameterUseCase:
    def __init__(self, repository: IParameterRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateParameterSchema) -> ParameterSchema:
        if data.data_type not in VALID_DATA_TYPES:
            raise ValidationAppException(
                AppErrorCode.PARAM_INVALID_DATA_TYPE,
                override_detail=f"Data type '{data.data_type}' is not supported. Valid: {', '.join(sorted(VALID_DATA_TYPES))}.",
            )
        DataTypeValueValidator.validate(data.value, data.data_type)

        existing = self.repository.get_by_code(data.code)
        if existing:
            raise ConflictException(
                AppErrorCode.PARAM_DUPLICATE_CODE,
                override_detail=f"A parameter with code '{data.code}' already exists.",
            )
        result = self.repository.create(data)
        invalidate_cache('parameters:*')
        _bump_runtime_caches(data.code)
        return result


class UpdateParameterUseCase:
    def __init__(self, repository: IParameterRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, data: UpdateParameterSchema) -> ParameterSchema:
        existing_param = self.repository.get_by_id(id)
        if not existing_param:
            raise NotFoundException(AppErrorCode.PARAM_NOT_FOUND)

        # Determine effective data_type and value for validation
        effective_data_type = data.data_type if data.data_type is not None else existing_param.data_type
        effective_value = data.value if data.value is not None else existing_param.value

        if data.data_type is not None and data.data_type not in VALID_DATA_TYPES:
            raise ValidationAppException(
                AppErrorCode.PARAM_INVALID_DATA_TYPE,
                override_detail=f"Data type '{data.data_type}' is not supported. Valid: {', '.join(sorted(VALID_DATA_TYPES))}.",
            )

        # Validate when value or data_type changes
        if data.value is not None or data.data_type is not None:
            DataTypeValueValidator.validate(effective_value, effective_data_type)

        if data.code is not None:
            existing = self.repository.get_by_code(data.code)
            if existing and existing.id != id:
                raise ConflictException(
                    AppErrorCode.PARAM_DUPLICATE_CODE,
                    override_detail=f"A parameter with code '{data.code}' already exists.",
                )

        result = self.repository.update(id, data)
        if not result:
            raise NotFoundException(AppErrorCode.PARAM_NOT_FOUND)
        invalidate_cache('parameters:*')
        _bump_runtime_caches(existing_param.code)
        if data.code and data.code != existing_param.code:
            _bump_runtime_caches(data.code)
        return result


class DeleteParameterUseCase:
    def __init__(self, repository: IParameterRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        existing = self.repository.get_by_id(id)
        if not existing:
            raise NotFoundException(AppErrorCode.PARAM_NOT_FOUND)
        deleted = self.repository.delete(id)
        if not deleted:
            raise NotFoundException(AppErrorCode.PARAM_NOT_FOUND)
        invalidate_cache('parameters:*')
        _bump_runtime_caches(existing.code)
        return deleted
