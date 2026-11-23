from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

MAX_FILTERS_PER_MODULE = 20
MAX_ZONES_PER_FILTER = 50


class ModuleKey(str, Enum):
    WAREHOUSE = 'warehouse'
    RECEIVING_RECEIPTS = 'receiving.receipts'
    RECEIVING_PUTAWAY = 'receiving.putaway'


def _dedupe(ids: list[UUID]) -> list[UUID]:
    seen: set[UUID] = set()
    return [item for item in ids if not (item in seen or seen.add(item))]


def _clean_name(value: str) -> str:
    cleaned = ' '.join(value.split())
    if not cleaned:
        raise ValueError('name must not be blank')
    return cleaned


class FilterCriteria(BaseModel):
    """Alcance del filtro: una bodega y, opcionalmente, un subconjunto de zonas.

    ``zone_ids`` vacío significa todas las zonas de la bodega.
    """

    warehouse_id: UUID
    zone_ids: list[UUID] = Field(default_factory=list, max_length=MAX_ZONES_PER_FILTER)

    @field_validator('zone_ids')
    @classmethod
    def _unique_zones(cls, value: list[UUID]) -> list[UUID]:
        return _dedupe(value)


class ModuleFilterInput(BaseModel):
    module_key: ModuleKey
    name: str = Field(min_length=1, max_length=80)
    criteria: FilterCriteria
    activate: bool = False

    @field_validator('name')
    @classmethod
    def _name(cls, value: str) -> str:
        return _clean_name(value)


class ModuleFilterPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    criteria: Optional[FilterCriteria] = None

    @field_validator('name')
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _clean_name(value)


class ModuleFilterRecord(BaseModel):
    """Fila persistida tal cual (sin enriquecer)."""

    id: UUID
    module_key: ModuleKey
    name: str
    criteria: FilterCriteria
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FacilityLabels(BaseModel):
    """Nombres vigentes de bodegas/zonas; solo incluye bodegas activas."""

    warehouses: dict[UUID, str] = Field(default_factory=dict)
    zones: dict[UUID, str] = Field(default_factory=dict)


class ModuleFilterSchema(ModuleFilterRecord):
    warehouse_name: Optional[str] = None
    zone_names: list[str] = Field(default_factory=list)
    available: bool = True


class ModuleFilterListSchema(BaseModel):
    items: list[ModuleFilterSchema]
    active_id: Optional[UUID] = None
