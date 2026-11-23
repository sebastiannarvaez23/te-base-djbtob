"""Catálogo por tipo de entidad. Para extender: valor nuevo en
``EntityScopeType`` + su catálogo en ``_CATALOGS``."""
from typing import Callable

from core.errors import AppErrorCode, NotFoundException
from client.features.security.access.entity_grants.domain.interfaces import IGrantableCatalog
from client.features.security.access.entity_grants.domain.schemas import GrantEntityType, entity_type_key


_CATALOGS: dict[GrantEntityType, Callable[[], IGrantableCatalog]] = {}


def catalog_for(entity_type: GrantEntityType) -> IGrantableCatalog:
    factory = _CATALOGS.get(entity_type)
    if factory is None:
        raise NotFoundException(
            AppErrorCode.GRANT_ENTITY_NOT_FOUND,
            context={'entity_type': entity_type_key(entity_type)},
        )
    return factory()
