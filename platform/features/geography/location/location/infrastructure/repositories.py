"""Repositorio Django — maestra geográfica."""

from __future__ import annotations

from typing import List, Optional, Tuple
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Q

from core.errors import AppErrorCode, ConflictException, NotFoundException
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
from ..models import City, Country, Department


def _country_schema(obj: Country) -> CountrySchema:
    return CountrySchema(
        id=obj.id,
        code=obj.code,
        name=obj.name,
        latitude=obj.latitude,
        longitude=obj.longitude,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _department_schema(obj: Department) -> DepartmentSchema:
    return DepartmentSchema(
        id=obj.id,
        country_id=obj.country_id,
        country_code=getattr(obj.country, 'code', '') if getattr(obj, 'country', None) else '',
        code=obj.code,
        name=obj.name,
        latitude=obj.latitude,
        longitude=obj.longitude,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _city_schema(obj: City) -> CitySchema:
    dept = getattr(obj, 'department', None)
    country = getattr(dept, 'country', None) if dept else None
    return CitySchema(
        id=obj.id,
        department_id=obj.department_id,
        department_code=dept.code if dept else '',
        country_id=country.id if country else None,
        country_code=country.code if country else '',
        code=obj.code,
        name=obj.name,
        latitude=obj.latitude,
        longitude=obj.longitude,
        is_active=obj.is_active,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )



def _paginate(qs, query: PaginatedQuery, mapper) -> PaginatedResult:
    if query.unpaginated:
        items = [mapper(row) for row in qs]
        total = len(items)
        return PaginatedResult(
            items=items,
            total=total,
            page=1,
            page_size=total or query.page_size,
            total_pages=1,
        )
    total = qs.count()
    rows = qs[query.offset: query.offset + query.page_size]
    items = [mapper(row) for row in rows]
    total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
    return PaginatedResult(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
        total_pages=total_pages,
    )


class DjangoGeographyRepository(IGeographyRepository):

    # ── Countries ──────────────────────────────────────────────────────────

    def _countries_qs(self, filters: Optional[dict] = None):
        qs = Country.objects.all()
        filters = filters or {}
        if filters.get('q'):
            q = filters['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        if filters.get('code'):
            qs = qs.filter(code__iexact=filters['code'])
        if filters.get('name'):
            qs = qs.filter(name__icontains=filters['name'])
        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])
        return qs.order_by('name')

    def list_countries(self, *, filters: Optional[dict] = None) -> List[CountrySchema]:
        return [_country_schema(row) for row in self._countries_qs(filters)]

    def list_countries_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        return _paginate(self._countries_qs(query.filters), query, _country_schema)

    def get_country(self, country_id: UUID) -> Optional[CountrySchema]:
        try:
            return _country_schema(Country.objects.get(id=country_id))
        except Country.DoesNotExist:
            return None

    def get_country_by_code(self, code: str) -> Optional[CountrySchema]:
        try:
            return _country_schema(Country.objects.get(code=code.strip().upper()))
        except Country.DoesNotExist:
            return None

    def create_country(self, data: CreateCountrySchema) -> CountrySchema:
        try:
            row = Country.objects.create(
                code=data.code,
                name=data.name,
                latitude=data.latitude,
                longitude=data.longitude,
                is_active=data.is_active,
            )
        except IntegrityError as exc:
            raise ConflictException(AppErrorCode.GEO_COUNTRY_DUPLICATE) from exc
        return _country_schema(row)

    def update_country(self, country_id: UUID, data: UpdateCountrySchema) -> Optional[CountrySchema]:
        try:
            row = Country.objects.get(id=country_id)
        except Country.DoesNotExist:
            return None
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(row, key, value)
        row.save()
        return _country_schema(row)

    def delete_country(self, country_id: UUID) -> bool:
        if not Country.objects.filter(id=country_id).exists():
            return False
        if Department.objects.filter(country_id=country_id).exists():
            raise ConflictException(AppErrorCode.GEO_COUNTRY_IN_USE)
        deleted, _ = Country.objects.filter(id=country_id).delete()
        return deleted > 0

    def upsert_country_by_code(self, data: CreateCountrySchema) -> Tuple[CountrySchema, bool]:
        row, created = Country.objects.update_or_create(
            code=data.code,
            defaults={
                'name': data.name,
                'latitude': data.latitude,
                'longitude': data.longitude,
                'is_active': data.is_active,
            },
        )
        return _country_schema(row), created

    # ── Departments ────────────────────────────────────────────────────────

    def _departments_qs(self, filters: Optional[dict] = None):
        qs = Department.objects.select_related('country').all()
        filters = filters or {}
        if filters.get('country_id'):
            qs = qs.filter(country_id=filters['country_id'])
        if filters.get('country_code'):
            qs = qs.filter(country__code__iexact=filters['country_code'])
        if filters.get('q'):
            q = filters['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])
        return qs.order_by('name')

    def list_departments(self, *, filters: Optional[dict] = None) -> List[DepartmentSchema]:
        return [_department_schema(row) for row in self._departments_qs(filters)]

    def list_departments_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        return _paginate(self._departments_qs(query.filters), query, _department_schema)

    def get_department(self, department_id: UUID) -> Optional[DepartmentSchema]:
        try:
            row = Department.objects.select_related('country').get(id=department_id)
            return _department_schema(row)
        except Department.DoesNotExist:
            return None

    def create_department(self, data: CreateDepartmentSchema) -> DepartmentSchema:
        if not Country.objects.filter(id=data.country_id).exists():
            raise NotFoundException(AppErrorCode.GEO_COUNTRY_NOT_FOUND)
        try:
            row = Department.objects.create(
                country_id=data.country_id,
                code=data.code,
                name=data.name,
                latitude=data.latitude,
                longitude=data.longitude,
                is_active=data.is_active,
            )
        except IntegrityError as exc:
            raise ConflictException(AppErrorCode.GEO_DEPARTMENT_DUPLICATE) from exc
        row = Department.objects.select_related('country').get(id=row.id)
        return _department_schema(row)

    def update_department(
        self, department_id: UUID, data: UpdateDepartmentSchema,
    ) -> Optional[DepartmentSchema]:
        try:
            row = Department.objects.select_related('country').get(id=department_id)
        except Department.DoesNotExist:
            return None
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(row, key, value)
        row.save()
        return _department_schema(row)

    def delete_department(self, department_id: UUID) -> bool:
        if not Department.objects.filter(id=department_id).exists():
            return False
        if City.objects.filter(department_id=department_id).exists():
            raise ConflictException(AppErrorCode.GEO_DEPARTMENT_IN_USE)
        deleted, _ = Department.objects.filter(id=department_id).delete()
        return deleted > 0

    def upsert_department(
        self, *, country_id: UUID, code: str, name: str,
        latitude=None, longitude=None, is_active: bool = True,
    ) -> Tuple[DepartmentSchema, bool]:
        row, created = Department.objects.update_or_create(
            country_id=country_id,
            code=code,
            defaults={
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'is_active': is_active,
            },
        )
        row = Department.objects.select_related('country').get(id=row.id)
        return _department_schema(row), created

    # ── Cities ─────────────────────────────────────────────────────────────

    def _cities_qs(self, filters: Optional[dict] = None):
        qs = City.objects.select_related('department', 'department__country').all()
        filters = filters or {}
        if filters.get('department_id'):
            qs = qs.filter(department_id=filters['department_id'])
        if filters.get('country_id'):
            qs = qs.filter(department__country_id=filters['country_id'])
        if filters.get('country_code'):
            qs = qs.filter(department__country__code__iexact=filters['country_code'])
        if filters.get('q'):
            q = filters['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])
        return qs.order_by('name')

    def list_cities(self, *, filters: Optional[dict] = None) -> List[CitySchema]:
        return [_city_schema(row) for row in self._cities_qs(filters)]

    def list_cities_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        return _paginate(self._cities_qs(query.filters), query, _city_schema)

    def get_city(self, city_id: UUID) -> Optional[CitySchema]:
        try:
            row = City.objects.select_related('department', 'department__country').get(id=city_id)
            return _city_schema(row)
        except City.DoesNotExist:
            return None

    def create_city(self, data: CreateCitySchema) -> CitySchema:
        if not Department.objects.filter(id=data.department_id).exists():
            raise NotFoundException(AppErrorCode.GEO_DEPARTMENT_NOT_FOUND)
        try:
            row = City.objects.create(
                department_id=data.department_id,
                code=data.code,
                name=data.name,
                latitude=data.latitude,
                longitude=data.longitude,
                is_active=data.is_active,
            )
        except IntegrityError as exc:
            raise ConflictException(AppErrorCode.GEO_CITY_DUPLICATE) from exc
        row = City.objects.select_related('department', 'department__country').get(id=row.id)
        return _city_schema(row)

    def update_city(self, city_id: UUID, data: UpdateCitySchema) -> Optional[CitySchema]:
        try:
            row = City.objects.select_related('department', 'department__country').get(id=city_id)
        except City.DoesNotExist:
            return None
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(row, key, value)
        row.save()
        return _city_schema(row)

    def delete_city(self, city_id: UUID) -> bool:
        if not City.objects.filter(id=city_id).exists():
            return False
        from platform.features.company.tenant.company.models import Company

        if Company.objects.filter(geo_city_id=city_id).exists():
            raise ConflictException(AppErrorCode.GEO_CITY_IN_USE)
        deleted, _ = City.objects.filter(id=city_id).delete()
        return deleted > 0

    def upsert_city(
        self, *, department_id: UUID, code: str, name: str,
        latitude=None, longitude=None, is_active: bool = True,
    ) -> Tuple[CitySchema, bool]:
        row, created = City.objects.update_or_create(
            department_id=department_id,
            code=code,
            defaults={
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'is_active': is_active,
            },
        )
        row = City.objects.select_related('department', 'department__country').get(id=row.id)
        return _city_schema(row), created
