"""Casos de uso — maestra geográfica."""

from __future__ import annotations

from typing import List, Optional, Union
from uuid import UUID

from core.errors import AppErrorCode, NotFoundException
from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.interfaces import IGeographyRepository
from ..domain.schemas import (
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
from core.trace import trace_layer


class ListCountriesUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        *,
        filters: Optional[dict] = None,
        query: Optional[PaginatedQuery] = None,
    ) -> Union[List[CountrySchema], PaginatedResult]:
        if query is not None:
            return self.repository.list_countries_paginated(query)
        return self.repository.list_countries(filters=filters)


class GetCountryUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, country_id: UUID) -> CountrySchema:
        row = self.repository.get_country(country_id)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_NOT_FOUND)
        return row


class CreateCountryUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateCountrySchema) -> CountrySchema:
        return self.repository.create_country(data)


class UpdateCountryUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, country_id: UUID, data: UpdateCountrySchema) -> CountrySchema:
        row = self.repository.update_country(country_id, data)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_NOT_FOUND)
        return row


class DeleteCountryUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, country_id: UUID) -> None:
        if not self.repository.delete_country(country_id):
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_NOT_FOUND)


class ListDepartmentsUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        *,
        filters: Optional[dict] = None,
        query: Optional[PaginatedQuery] = None,
    ) -> Union[List[DepartmentSchema], PaginatedResult]:
        if query is not None:
            return self.repository.list_departments_paginated(query)
        return self.repository.list_departments(filters=filters)


class GetDepartmentUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, department_id: UUID) -> DepartmentSchema:
        row = self.repository.get_department(department_id)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_DEPARTMENT_NOT_FOUND)
        return row


class CreateDepartmentUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateDepartmentSchema) -> DepartmentSchema:
        return self.repository.create_department(data)


class UpdateDepartmentUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, department_id: UUID, data: UpdateDepartmentSchema) -> DepartmentSchema:
        row = self.repository.update_department(department_id, data)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_DEPARTMENT_NOT_FOUND)
        return row


class DeleteDepartmentUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, department_id: UUID) -> None:
        if not self.repository.delete_department(department_id):
            raise NotFoundException(AppErrorCode.GEO_DEPARTMENT_NOT_FOUND)


class ListCitiesUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        *,
        filters: Optional[dict] = None,
        query: Optional[PaginatedQuery] = None,
    ) -> Union[List[CitySchema], PaginatedResult]:
        if query is not None:
            return self.repository.list_cities_paginated(query)
        return self.repository.list_cities(filters=filters)


class GetCityUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, city_id: UUID) -> CitySchema:
        row = self.repository.get_city(city_id)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_CITY_NOT_FOUND)
        return row


class CreateCityUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreateCitySchema) -> CitySchema:
        return self.repository.create_city(data)


class UpdateCityUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, city_id: UUID, data: UpdateCitySchema) -> CitySchema:
        row = self.repository.update_city(city_id, data)
        if not row:
            raise NotFoundException(AppErrorCode.GEO_CITY_NOT_FOUND)
        return row


class DeleteCityUseCase:
    def __init__(self, repository: IGeographyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, city_id: UUID) -> None:
        if not self.repository.delete_city(city_id):
            raise NotFoundException(AppErrorCode.GEO_CITY_NOT_FOUND)
