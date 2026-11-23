from __future__ import annotations

import uuid
from typing import List

from pydantic import ValidationError

from core.cache import invalidate_cache, use_case_cache
from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ValidationAppException,
)
from core.flags.domain.schemas import FlagDefinition

from ..domain.interfaces import IFeatureFlagRepository
from ..domain.schemas import (
    CreateFeatureFlagSchema,
    FeatureFlagSchema,
    UpdateFeatureFlagSchema,
)
from core.trace import trace_layer

_CACHE_PREFIX = 'feature_flags'


def _invalidate_flags_cache() -> None:
    # Clave exacta del listado + variantes con sufijo (detalle / snapshot).
    invalidate_cache(_CACHE_PREFIX)
    invalidate_cache(f'{_CACHE_PREFIX}:*')


def _validation_error(exc: ValidationError) -> ValidationAppException:
    detail = '; '.join(
        f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
        for err in exc.errors()
    )
    return ValidationAppException(
        AppErrorCode.FLAG_INVALID_PAYLOAD,
        override_detail=detail,
    )


class GetAllFeatureFlagsUseCase:
    def __init__(self, repository: IFeatureFlagRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=_CACHE_PREFIX)
    def execute(self, filters: dict | None = None) -> List[FeatureFlagSchema]:
        return self.repository.get_all(filters=filters)


class GetFeatureFlagByIdUseCase:
    def __init__(self, repository: IFeatureFlagRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=_CACHE_PREFIX)
    def execute(self, id: uuid.UUID) -> FeatureFlagSchema:
        result = self.repository.get_by_id(id)
        if not result:
            raise NotFoundException(AppErrorCode.FLAG_NOT_FOUND)
        return result


class GetActiveFlagsSnapshotUseCase:
    """Snapshot evaluable cacheado para el runtime de core/flags."""

    def __init__(self, repository: IFeatureFlagRepository):
        self.repository = repository

    @trace_layer('application')
    @use_case_cache(prefix=f'{_CACHE_PREFIX}:snapshot')
    def execute(self) -> List[FlagDefinition]:
        return self.repository.get_active_definitions()


class CreateFeatureFlagUseCase:
    def __init__(self, repository: IFeatureFlagRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateFeatureFlagSchema) -> FeatureFlagSchema:
        existing = self.repository.get_by_key(data.key)
        if existing:
            raise ConflictException(
                AppErrorCode.FLAG_DUPLICATE_KEY,
                override_detail=f"A feature flag with key '{data.key}' already exists.",
            )
        result = self.repository.create(data)
        _invalidate_flags_cache()
        return result


class UpdateFeatureFlagUseCase:
    def __init__(self, repository: IFeatureFlagRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, id: uuid.UUID, data: UpdateFeatureFlagSchema,
    ) -> FeatureFlagSchema:
        existing = self.repository.get_by_id(id)
        if not existing:
            raise NotFoundException(AppErrorCode.FLAG_NOT_FOUND)

        if data.key is not None:
            other = self.repository.get_by_key(data.key)
            if other and other.id != id:
                raise ConflictException(
                    AppErrorCode.FLAG_DUPLICATE_KEY,
                    override_detail=(
                        f"A feature flag with key '{data.key}' already exists."
                    ),
                )

        result = self.repository.update(id, data)
        if not result:
            raise NotFoundException(AppErrorCode.FLAG_NOT_FOUND)
        _invalidate_flags_cache()
        return result


class DeleteFeatureFlagUseCase:
    def __init__(self, repository: IFeatureFlagRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID) -> bool:
        deleted = self.repository.delete(id)
        if not deleted:
            raise NotFoundException(AppErrorCode.FLAG_NOT_FOUND)
        _invalidate_flags_cache()
        return deleted


class ToggleFeatureFlagEnabledUseCase:
    def __init__(self, repository: IFeatureFlagRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, enabled: bool) -> FeatureFlagSchema:
        return UpdateFeatureFlagUseCase(self.repository).execute(
            id, UpdateFeatureFlagSchema(enabled=enabled),
        )


class SetFeatureFlagStatusUseCase:
    def __init__(self, repository: IFeatureFlagRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, id: uuid.UUID, status: str) -> FeatureFlagSchema:
        try:
            data = UpdateFeatureFlagSchema(status=status)
        except ValidationError as exc:
            raise _validation_error(exc) from exc
        return UpdateFeatureFlagUseCase(self.repository).execute(id, data)
