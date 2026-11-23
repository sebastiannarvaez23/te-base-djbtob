"""Composition root of the entity_grants L4."""

from client.features.security.access.entity_grants.application.use_cases import (
    GetGrantSetUseCase,
    PurgeOrphanGrantsUseCase,
    ReplaceGrantSetUseCase,
)
from client.features.security.access.entity_grants.domain.schemas import GrantEntityType
from client.features.security.access.entity_grants.infrastructure.catalogs import catalog_for
from client.features.security.access.entity_grants.infrastructure.repositories import (
    DjangoEntityGrantRepository,
)
from client.features.security.access.entity_grants.infrastructure.scope_invalidator import (
    CacheGrantScopeInvalidator,
)
from client.features.security.access.entity_grants.infrastructure.user_directory import (
    DjangoCompanyUserDirectory,
)


def get_grant_set(entity_type: GrantEntityType) -> GetGrantSetUseCase:
    return GetGrantSetUseCase(
        DjangoEntityGrantRepository(), DjangoCompanyUserDirectory(), catalog_for(entity_type),
    )


def purge_orphan_grants() -> PurgeOrphanGrantsUseCase:
    return PurgeOrphanGrantsUseCase(DjangoEntityGrantRepository(), DjangoCompanyUserDirectory(), catalog_for)


def replace_grant_set(entity_type: GrantEntityType) -> ReplaceGrantSetUseCase:
    return ReplaceGrantSetUseCase(
        DjangoEntityGrantRepository(),
        DjangoCompanyUserDirectory(),
        catalog_for(entity_type),
        CacheGrantScopeInvalidator(),
    )
