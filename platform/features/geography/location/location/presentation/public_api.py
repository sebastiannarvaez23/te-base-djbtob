"""Public geography catalog — read-only active countries / departments / cities.

Consumed by the onboarding wizard (anonymous). Admin CRUD stays under
``platform/locations/`` with AdminTokenAuthentication.
"""

from __future__ import annotations

from rest_framework.views import APIView

from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query

from platform.features.geography.location.location.application.use_cases import (
    ListCitiesUseCase,
    ListCountriesUseCase,
    ListDepartmentsUseCase,
)
from platform.features.geography.location.location.infrastructure.repositories import (
    DjangoGeographyRepository,
)
from platform.features.geography.location.location.presentation.queries import (
    CityListQuery,
    CountryListQuery,
    DepartmentListQuery,
)

_PUBLIC_COUNTRY_FIELDS = ('id', 'code', 'name')
_PUBLIC_DEPARTMENT_FIELDS = ('id', 'code', 'name', 'country_id', 'country_code')
_PUBLIC_CITY_FIELDS = (
    'id', 'code', 'name', 'department_id', 'department_code', 'country_id', 'country_code',
)


def _repo():
    return DjangoGeographyRepository()


def _project(items, fields: tuple[str, ...]):
    return [
        {k: v for k, v in item.model_dump(mode='json').items() if k in fields}
        for item in items
    ]


class PublicCountryCatalogView(APIView):
    """``GET /api/v1/locations/countries/`` — active countries."""

    authentication_classes = []
    permission_classes = []

    @validated_query(CountryListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        filters = {**(query.filters or {}), 'is_active': True}
        items = ListCountriesUseCase(_repo()).execute(filters=filters)
        return wrap_response(_project(items, _PUBLIC_COUNTRY_FIELDS))


class PublicDepartmentCatalogView(APIView):
    """``GET /api/v1/locations/departments/`` — active departments."""

    authentication_classes = []
    permission_classes = []

    @validated_query(DepartmentListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        filters = {**(query.filters or {}), 'is_active': True}
        items = ListDepartmentsUseCase(_repo()).execute(filters=filters)
        return wrap_response(_project(items, _PUBLIC_DEPARTMENT_FIELDS))


class PublicCityCatalogView(APIView):
    """``GET /api/v1/locations/cities/`` — active cities."""

    authentication_classes = []
    permission_classes = []

    @validated_query(CityListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        filters = {**(query.filters or {}), 'is_active': True}
        items = ListCitiesUseCase(_repo()).execute(filters=filters)
        return wrap_response(_project(items, _PUBLIC_CITY_FIELDS))
