from abc import ABC, abstractmethod
from typing import Iterable, Optional
from uuid import UUID

from client.features.security.access.entity_grants.domain.schemas import (
    GrantAxis,
    GrantDiff,
    GrantEntityType,
    GrantScope,
)


class IEntityGrantRepository(ABC):

    @abstractmethod
    def list_ids(self, scope: GrantScope) -> set[UUID]:
        """Valores del conjunto: entidades (eje usuario) o usuarios (eje entidad)."""

    @abstractmethod
    def replace(self, scope: GrantScope, ids: list[UUID], granted_by: Optional[UUID]) -> GrantDiff:
        """Deja exactamente ``ids`` en el conjunto; atómico y serializado por tipo."""

    @abstractmethod
    def granted_keys(self, entity_type: GrantEntityType, axis: GrantAxis) -> set[UUID]:
        """IDs distintos con algún acceso: usuarios (eje usuario) o entidades (eje entidad)."""

    @abstractmethod
    def delete_keys(
        self, entity_type: GrantEntityType, user_ids: Iterable[UUID], entity_ids: Iterable[UUID],
    ) -> int:
        """Borra los accesos de esos usuarios o entidades; atómico y serializado por tipo."""


class IGrantableCatalog(ABC):
    """Entidades de un tipo que existen (almacenes, zonas, …)."""

    @abstractmethod
    def existing_ids(self, ids: Iterable[UUID]) -> set[UUID]: ...


class ICompanyUserDirectory(ABC):
    """Usuarios de la empresa (schema público)."""

    @abstractmethod
    def member_ids(self, company_id: UUID, ids: Iterable[UUID]) -> set[UUID]: ...


class IGrantScopeInvalidator(ABC):

    @abstractmethod
    def invalidate(self, user_ids: Iterable[UUID], entity_type: GrantEntityType) -> None: ...
