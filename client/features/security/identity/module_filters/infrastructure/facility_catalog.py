from uuid import UUID

from client.features.security.identity.module_filters.domain.interfaces import IFacilityCatalog
from client.features.security.identity.module_filters.domain.schemas import FacilityLabels


class DjangoFacilityCatalog(IFacilityCatalog):
    """Sin catálogo de producto: ningún registro existe hasta que un dominio lo implemente."""

    def active_warehouse_exists(self, warehouse_id: UUID) -> bool:
        return False

    def zones_in_warehouse(self, warehouse_id: UUID, zone_ids: list[UUID]) -> set[UUID]:
        return set()

    def labels(self, warehouse_ids: set[UUID], zone_ids: set[UUID]) -> FacilityLabels:
        return FacilityLabels(warehouses={}, zones={})
