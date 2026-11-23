from uuid import UUID

from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ValidationAppException,
)
from client.features.security.identity.module_filters.domain.interfaces import (
    IFacilityCatalog,
    IModuleFilterRepository,
)
from client.features.security.identity.module_filters.domain.schemas import (
    MAX_FILTERS_PER_MODULE,
    FacilityLabels,
    FilterCriteria,
    ModuleFilterInput,
    ModuleFilterListSchema,
    ModuleFilterPatch,
    ModuleFilterRecord,
    ModuleFilterSchema,
    ModuleKey,
)


def _assert_criteria(catalog: IFacilityCatalog, criteria: FilterCriteria) -> None:
    if not catalog.active_warehouse_exists(criteria.warehouse_id):
        raise ValidationAppException(
            AppErrorCode.MFLT_WAREHOUSE_UNAVAILABLE,
            context={'warehouse_id': str(criteria.warehouse_id)},
        )
    if not criteria.zone_ids:
        return
    found = catalog.zones_in_warehouse(criteria.warehouse_id, criteria.zone_ids)
    missing = [str(item) for item in criteria.zone_ids if item not in found]
    if missing:
        raise ValidationAppException(
            AppErrorCode.MFLT_ZONE_OUTSIDE_WAREHOUSE,
            context={'zone_ids': missing},
        )


def _enrich(records: list[ModuleFilterRecord], catalog: IFacilityCatalog) -> list[ModuleFilterSchema]:
    if not records:
        return []
    labels: FacilityLabels = catalog.labels(
        {item.criteria.warehouse_id for item in records},
        {zone for item in records for zone in item.criteria.zone_ids},
    )
    result: list[ModuleFilterSchema] = []
    for record in records:
        warehouse_name = labels.warehouses.get(record.criteria.warehouse_id)
        result.append(ModuleFilterSchema(
            **record.model_dump(),
            warehouse_name=warehouse_name,
            zone_names=[
                labels.zones[zone] for zone in record.criteria.zone_ids if zone in labels.zones
            ],
            available=warehouse_name is not None,
        ))
    return result


def _get_owned(repository: IModuleFilterRepository, user_id: UUID, filter_id: UUID) -> ModuleFilterRecord:
    record = repository.get(user_id, filter_id)
    if record is None:
        raise NotFoundException(
            AppErrorCode.MFLT_NOT_FOUND,
            context={'filter_id': str(filter_id)},
        )
    return record


def _assert_name_free(
    repository: IModuleFilterRepository,
    user_id: UUID,
    module_key: ModuleKey,
    name: str,
    exclude_id: UUID | None = None,
) -> None:
    if repository.name_taken(user_id, module_key, name, exclude_id):
        raise ConflictException(AppErrorCode.MFLT_DUPLICATE_NAME, context={'name': name})


class ListModuleFiltersUseCase:
    def __init__(self, repository: IModuleFilterRepository, catalog: IFacilityCatalog):
        self.repository = repository
        self.catalog = catalog

    def execute(self, user_id: UUID, module_key: ModuleKey) -> ModuleFilterListSchema:
        items = _enrich(self.repository.list_for_user(user_id, module_key), self.catalog)
        active = next((item for item in items if item.is_active), None)
        return ModuleFilterListSchema(items=items, active_id=active.id if active else None)


class CreateModuleFilterUseCase:
    def __init__(self, repository: IModuleFilterRepository, catalog: IFacilityCatalog):
        self.repository = repository
        self.catalog = catalog

    def execute(self, user_id: UUID, data: ModuleFilterInput) -> ModuleFilterSchema:
        if self.repository.count_for_user(user_id, data.module_key) >= MAX_FILTERS_PER_MODULE:
            raise ConflictException(
                AppErrorCode.MFLT_LIMIT_REACHED,
                context={'limit': MAX_FILTERS_PER_MODULE},
            )
        _assert_name_free(self.repository, user_id, data.module_key, data.name)
        _assert_criteria(self.catalog, data.criteria)
        record = self.repository.create(user_id, data)
        return _enrich([record], self.catalog)[0]


class UpdateModuleFilterUseCase:
    def __init__(self, repository: IModuleFilterRepository, catalog: IFacilityCatalog):
        self.repository = repository
        self.catalog = catalog

    def execute(self, user_id: UUID, filter_id: UUID, data: ModuleFilterPatch) -> ModuleFilterSchema:
        current = _get_owned(self.repository, user_id, filter_id)
        if data.name is not None and data.name != current.name:
            _assert_name_free(self.repository, user_id, current.module_key, data.name, filter_id)
        if data.criteria is not None:
            _assert_criteria(self.catalog, data.criteria)
        record = self.repository.update(user_id, filter_id, data.name, data.criteria)
        return _enrich([record], self.catalog)[0]


class DeleteModuleFilterUseCase:
    def __init__(self, repository: IModuleFilterRepository):
        self.repository = repository

    def execute(self, user_id: UUID, filter_id: UUID) -> None:
        _get_owned(self.repository, user_id, filter_id)
        self.repository.delete(user_id, filter_id)


class ActivateModuleFilterUseCase:
    def __init__(self, repository: IModuleFilterRepository, catalog: IFacilityCatalog):
        self.repository = repository
        self.catalog = catalog

    def execute(self, user_id: UUID, filter_id: UUID) -> ModuleFilterSchema:
        current = _get_owned(self.repository, user_id, filter_id)
        _assert_criteria(self.catalog, current.criteria)
        record = self.repository.activate(user_id, filter_id)
        return _enrich([record], self.catalog)[0]


class DeactivateModuleFiltersUseCase:
    def __init__(self, repository: IModuleFilterRepository):
        self.repository = repository

    def execute(self, user_id: UUID, module_key: ModuleKey) -> int:
        return self.repository.deactivate_all(user_id, module_key)
