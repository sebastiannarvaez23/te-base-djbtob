from typing import Callable, Optional
from uuid import UUID

from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from core.trace import trace_layer
from client.features.security.access.entity_grants.domain.interfaces import (
    ICompanyUserDirectory,
    IEntityGrantRepository,
    IGrantableCatalog,
    IGrantScopeInvalidator,
)
from client.features.security.access.entity_grants.domain.schemas import (
    GrantAxis,
    GrantChangeSchema,
    GrantDiff,
    GrantEntityType,
    GrantScope,
    entity_type_key,
    GrantSetInput,
    GrantSetSchema,
    OrphanPurgeSchema,
)


class _GrantTargets:
    """Valida clave y valores del conjunto según el eje (usuario ↔ entidad)."""

    def __init__(self, company_id: UUID, directory: ICompanyUserDirectory, catalog: IGrantableCatalog):
        self.company_id = company_id
        self.directory = directory
        self.catalog = catalog

    def _users(self, ids: list[UUID]) -> set[UUID]:
        return self.directory.member_ids(self.company_id, ids) if ids else set()

    def _entities(self, ids: list[UUID]) -> set[UUID]:
        return self.catalog.existing_ids(ids) if ids else set()

    def assert_key(self, scope: GrantScope) -> None:
        if scope.axis is GrantAxis.USER:
            found, code = self._users([scope.key_id]), AppErrorCode.USER_NOT_FOUND
        else:
            found, code = self._entities([scope.key_id]), AppErrorCode.GRANT_ENTITY_NOT_FOUND
        if scope.key_id not in found:
            raise NotFoundException(code, context={'entity_type': entity_type_key(scope.entity_type), 'id': str(scope.key_id)})

    def assert_values(self, scope: GrantScope, ids: list[UUID]) -> None:
        if scope.axis is GrantAxis.USER:
            found, code = self._entities(ids), AppErrorCode.GRANT_ENTITY_UNAVAILABLE
        else:
            found, code = self._users(ids), AppErrorCode.GRANT_USER_OUTSIDE_COMPANY
        missing = [str(item) for item in ids if item not in found]
        if missing:
            raise ValidationAppException(code, context={'entity_type': entity_type_key(scope.entity_type), 'ids': missing})


def _affected_users(scope: GrantScope, diff: GrantDiff) -> list[UUID]:
    if scope.axis is GrantAxis.USER:
        return [scope.key_id]
    return [*diff.added, *diff.removed]


def _sorted(ids) -> list[UUID]:
    return sorted(ids, key=str)


class GetGrantSetUseCase:
    def __init__(
        self,
        repository: IEntityGrantRepository,
        directory: ICompanyUserDirectory,
        catalog: IGrantableCatalog,
    ):
        self.repository = repository
        self.directory = directory
        self.catalog = catalog

    @trace_layer('application')
    def execute(self, company_id: UUID, scope: GrantScope) -> GrantSetSchema:
        _GrantTargets(company_id, self.directory, self.catalog).assert_key(scope)
        return GrantSetSchema(
            **scope.model_dump(),
            ids=_sorted(self.repository.list_ids(scope)),
        )


class PurgeOrphanGrantsUseCase:
    """Quita accesos de usuarios fuera de la empresa o de entidades que ya no existen."""

    def __init__(
        self,
        repository: IEntityGrantRepository,
        directory: ICompanyUserDirectory,
        catalogs: Callable[[GrantEntityType], IGrantableCatalog],
    ):
        self.repository = repository
        self.directory = directory
        self.catalogs = catalogs

    @trace_layer('application')
    def execute(self, company_id: UUID, dry_run: bool = False) -> list[OrphanPurgeSchema]:
        return [self._purge(company_id, entity_type, dry_run) for entity_type in GrantEntityType]

    def _purge(self, company_id: UUID, entity_type: GrantEntityType, dry_run: bool) -> OrphanPurgeSchema:
        users = self.repository.granted_keys(entity_type, GrantAxis.USER)
        entities = self.repository.granted_keys(entity_type, GrantAxis.ENTITY)
        result = OrphanPurgeSchema(
            entity_type=entity_type,
            missing_users=_sorted(users - (self.directory.member_ids(company_id, users) if users else set())),
            missing_entities=_sorted(
                entities - (self.catalogs(entity_type).existing_ids(entities) if entities else set()),
            ),
        )
        if dry_run or not result.found:
            return result
        deleted = self.repository.delete_keys(entity_type, result.missing_users, result.missing_entities)
        return result.model_copy(update={'deleted': deleted})


class ReplaceGrantSetUseCase:
    def __init__(
        self,
        repository: IEntityGrantRepository,
        directory: ICompanyUserDirectory,
        catalog: IGrantableCatalog,
        invalidator: IGrantScopeInvalidator,
    ):
        self.repository = repository
        self.directory = directory
        self.catalog = catalog
        self.invalidator = invalidator

    @trace_layer('application')
    def execute(
        self,
        company_id: UUID,
        scope: GrantScope,
        data: GrantSetInput,
        granted_by: Optional[UUID],
    ) -> GrantChangeSchema:
        targets = _GrantTargets(company_id, self.directory, self.catalog)
        targets.assert_key(scope)
        targets.assert_values(scope, data.ids)
        diff = self.repository.replace(scope, data.ids, granted_by)
        if diff.changed:
            self.invalidator.invalidate(_affected_users(scope, diff), scope.entity_type)
        return GrantChangeSchema(
            **scope.model_dump(),
            ids=_sorted(data.ids),
            added=diff.added,
            removed=diff.removed,
        )
