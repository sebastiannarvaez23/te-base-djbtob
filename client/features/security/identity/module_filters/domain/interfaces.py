from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from client.features.security.identity.module_filters.domain.schemas import (
    FacilityLabels,
    FilterCriteria,
    ModuleFilterInput,
    ModuleFilterRecord,
    ModuleKey,
)


class IModuleFilterRepository(ABC):

    @abstractmethod
    def list_for_user(self, user_id: UUID, module_key: ModuleKey) -> list[ModuleFilterRecord]: ...

    @abstractmethod
    def get(self, user_id: UUID, filter_id: UUID) -> Optional[ModuleFilterRecord]: ...

    @abstractmethod
    def count_for_user(self, user_id: UUID, module_key: ModuleKey) -> int: ...

    @abstractmethod
    def name_taken(
        self, user_id: UUID, module_key: ModuleKey, name: str, exclude_id: Optional[UUID] = None,
    ) -> bool: ...

    @abstractmethod
    def create(self, user_id: UUID, data: ModuleFilterInput) -> ModuleFilterRecord:
        """Crea el filtro; si ``data.activate`` desactiva los demás del módulo (atómico)."""

    @abstractmethod
    def update(
        self, user_id: UUID, filter_id: UUID, name: Optional[str], criteria: Optional[FilterCriteria],
    ) -> ModuleFilterRecord: ...

    @abstractmethod
    def delete(self, user_id: UUID, filter_id: UUID) -> None: ...

    @abstractmethod
    def activate(self, user_id: UUID, filter_id: UUID) -> ModuleFilterRecord:
        """Activa uno y desactiva el resto del mismo módulo (atómico)."""

    @abstractmethod
    def deactivate_all(self, user_id: UUID, module_key: ModuleKey) -> int: ...


class IFacilityCatalog(ABC):
    """Puerto de solo lectura hacia bodegas/zonas (feature warehouse)."""

    @abstractmethod
    def active_warehouse_exists(self, warehouse_id: UUID) -> bool: ...

    @abstractmethod
    def zones_in_warehouse(self, warehouse_id: UUID, zone_ids: list[UUID]) -> set[UUID]:
        """Subconjunto de ``zone_ids`` que pertenece a la bodega."""

    @abstractmethod
    def labels(self, warehouse_ids: set[UUID], zone_ids: set[UUID]) -> FacilityLabels: ...
