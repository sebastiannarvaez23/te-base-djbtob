from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from core.query.core import PaginatedQuery, PaginatedResult

from .schemas import (
    CitySchema,
    CountrySchema,
    CreateCitySchema,
    CreateCountrySchema,
    CreateDepartmentSchema,
    DepartmentSchema,
    UpdateCitySchema,
    UpdateCountrySchema,
    UpdateDepartmentSchema,
)


class IGeographyRepository(ABC):

    # ── Countries ──────────────────────────────────────────────────────────

    @abstractmethod
    def list_countries(self, *, filters: Optional[dict] = None) -> List[CountrySchema]:
        ...

    @abstractmethod
    def list_countries_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def get_country(self, country_id: UUID) -> Optional[CountrySchema]:
        ...

    @abstractmethod
    def get_country_by_code(self, code: str) -> Optional[CountrySchema]:
        ...

    @abstractmethod
    def create_country(self, data: CreateCountrySchema) -> CountrySchema:
        ...

    @abstractmethod
    def update_country(self, country_id: UUID, data: UpdateCountrySchema) -> Optional[CountrySchema]:
        ...

    @abstractmethod
    def delete_country(self, country_id: UUID) -> bool:
        ...

    @abstractmethod
    def upsert_country_by_code(self, data: CreateCountrySchema) -> tuple[CountrySchema, bool]:
        """Returns (row, created)."""
        ...

    # ── Departments ────────────────────────────────────────────────────────

    @abstractmethod
    def list_departments(self, *, filters: Optional[dict] = None) -> List[DepartmentSchema]:
        ...

    @abstractmethod
    def list_departments_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def get_department(self, department_id: UUID) -> Optional[DepartmentSchema]:
        ...

    @abstractmethod
    def create_department(self, data: CreateDepartmentSchema) -> DepartmentSchema:
        ...

    @abstractmethod
    def update_department(
        self, department_id: UUID, data: UpdateDepartmentSchema,
    ) -> Optional[DepartmentSchema]:
        ...

    @abstractmethod
    def delete_department(self, department_id: UUID) -> bool:
        ...

    @abstractmethod
    def upsert_department(
        self, *, country_id: UUID, code: str, name: str,
        latitude=None, longitude=None, is_active: bool = True,
    ) -> tuple[DepartmentSchema, bool]:
        ...

    # ── Cities ─────────────────────────────────────────────────────────────

    @abstractmethod
    def list_cities(self, *, filters: Optional[dict] = None) -> List[CitySchema]:
        ...

    @abstractmethod
    def list_cities_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def get_city(self, city_id: UUID) -> Optional[CitySchema]:
        ...

    @abstractmethod
    def create_city(self, data: CreateCitySchema) -> CitySchema:
        ...

    @abstractmethod
    def update_city(self, city_id: UUID, data: UpdateCitySchema) -> Optional[CitySchema]:
        ...

    @abstractmethod
    def delete_city(self, city_id: UUID) -> bool:
        ...

    @abstractmethod
    def upsert_city(
        self, *, department_id: UUID, code: str, name: str,
        latitude=None, longitude=None, is_active: bool = True,
    ) -> tuple[CitySchema, bool]:
        ...
