import uuid
from typing import List

from core.admin_parameters import clear_admin_parameter_cache
from core.auth.inactivity import clear_inactivity_cache
from core.cache import invalidate_cache, use_case_cache
from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ValidationAppException,
)
from core.trace import trace_layer
from core.validators import DataTypeValueValidator

from ..domain.enums import DataType
from ..domain.interfaces import IAdminParameterRepository
from ..domain.schemas import (
    AdminParameterSchema,
    CreateAdminParameterSchema,
    UpdateAdminParameterSchema,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.domain.interfaces import (
    IAdminParameterTypeRepository,
)

VALID_DATA_TYPES = {dt.value for dt in DataType}
_CACHE_PREFIX = 'admin_parameters'
_IDLE_PARAM = 'TIME_INACTIVITY'


def _bump_runtime_caches(*codes: str) -> None:
    for code in codes:
        if code:
            clear_admin_parameter_cache(code)
            if code == _IDLE_PARAM:
                clear_inactivity_cache()


class GetAllAdminParametersUseCase:
    def __init__(self, repository: IAdminParameterRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=_CACHE_PREFIX)
    def execute(self, filters: dict | None = None) -> List[AdminParameterSchema]:
        return self.repository.get_all(filters=filters)


class GetAdminParameterByIdUseCase:
    def __init__(self, repository: IAdminParameterRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=_CACHE_PREFIX)
    def execute(self, id: uuid.UUID) -> AdminParameterSchema:
        result = self.repository.get_by_id(id)
        if not result:
            raise NotFoundException(AppErrorCode.APARAM_NOT_FOUND)
        return result


class CreateAdminParameterUseCase:
    def __init__(
        self,
        repository: IAdminParameterRepository,
        type_repository: IAdminParameterTypeRepository,
    ):
        self.repository = repository
        self.type_repository = type_repository

    @trace_layer('application')
    def execute(self, data: CreateAdminParameterSchema) -> AdminParameterSchema:
        if not self.type_repository.get_by_id(data.parameter_type):
            raise NotFoundException(AppErrorCode.APTYPE_NOT_FOUND)

        if data.data_type not in VALID_DATA_TYPES:
            raise ValidationAppException(
                AppErrorCode.APARAM_INVALID_DATA_TYPE,
                override_detail=(
                    f"Data type '{data.data_type}' is not supported. "
                    f"Valid: {', '.join(sorted(VALID_DATA_TYPES))}."
                ),
            )
        DataTypeValueValidator.validate(
            data.value,
            data.data_type,
            error_code=AppErrorCode.APARAM_INVALID_VALUE,
        )

        existing = self.repository.get_by_code(data.code)
        if existing:
            raise ConflictException(
                AppErrorCode.APARAM_DUPLICATE_CODE,
                override_detail=(
                    f"An admin parameter with code '{data.code}' already exists."
                ),
            )
        result = self.repository.create(data)
        invalidate_cache(f'{_CACHE_PREFIX}:*')
        _bump_runtime_caches(data.code)
        return result


class UpdateAdminParameterUseCase:
    def __init__(
        self,
        repository: IAdminParameterRepository,
        type_repository: IAdminParameterTypeRepository | None = None,
    ):
        self.repository = repository
        self.type_repository = type_repository

    @trace_layer('application')
    def execute(
        self, id: uuid.UUID, data: UpdateAdminParameterSchema,
    ) -> AdminParameterSchema:
        existing_param = self.repository.get_by_id(id)
        if not existing_param:
            raise NotFoundException(AppErrorCode.APARAM_NOT_FOUND)

        if data.parameter_type is not None:
            if self.type_repository is None or not self.type_repository.get_by_id(
                data.parameter_type,
            ):
                raise NotFoundException(AppErrorCode.APTYPE_NOT_FOUND)

        effective_data_type = (
            data.data_type if data.data_type is not None else existing_param.data_type
        )
        effective_value = data.value if data.value is not None else existing_param.value

        if data.data_type is not None and data.data_type not in VALID_DATA_TYPES:
            raise ValidationAppException(
                AppErrorCode.APARAM_INVALID_DATA_TYPE,
                override_detail=(
                    f"Data type '{data.data_type}' is not supported. "
                    f"Valid: {', '.join(sorted(VALID_DATA_TYPES))}."
                ),
            )

        if data.value is not None or data.data_type is not None:
            DataTypeValueValidator.validate(
                effective_value,
                effective_data_type,
                error_code=AppErrorCode.APARAM_INVALID_VALUE,
            )

        if data.code is not None:
            existing = self.repository.get_by_code(data.code)
            if existing and existing.id != id:
                raise ConflictException(
                    AppErrorCode.APARAM_DUPLICATE_CODE,
                    override_detail=(
                        f"An admin parameter with code '{data.code}' already exists."
                    ),
                )

        result = self.repository.update(id, data)
        if not result:
            raise NotFoundException(AppErrorCode.APARAM_NOT_FOUND)
        invalidate_cache(f'{_CACHE_PREFIX}:*')
        _bump_runtime_caches(existing_param.code)
        if data.code and data.code != existing_param.code:
            _bump_runtime_caches(data.code)
        return result


class DeleteAdminParameterUseCase:
    def __init__(self, repository: IAdminParameterRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        existing = self.repository.get_by_id(id)
        if not existing:
            raise NotFoundException(AppErrorCode.APARAM_NOT_FOUND)
        deleted = self.repository.delete(id)
        if not deleted:
            raise NotFoundException(AppErrorCode.APARAM_NOT_FOUND)
        invalidate_cache(f'{_CACHE_PREFIX}:*')
        _bump_runtime_caches(existing.code)
        return deleted
