"""API admin — maestra geográfica (países / departamentos / ciudades)."""

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, ValidationAppException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.geography.location.location.application.import_use_cases import (
    ImportLocationsUseCase,
)
from platform.features.geography.location.location.infrastructure.excel_template import (
    build_location_import_template,
)
from platform.features.geography.location.location.application.use_cases import (
    CreateCityUseCase,
    CreateCountryUseCase,
    CreateDepartmentUseCase,
    DeleteCityUseCase,
    DeleteCountryUseCase,
    DeleteDepartmentUseCase,
    GetCityUseCase,
    GetCountryUseCase,
    GetDepartmentUseCase,
    ListCitiesUseCase,
    ListCountriesUseCase,
    ListDepartmentsUseCase,
    UpdateCityUseCase,
    UpdateCountryUseCase,
    UpdateDepartmentUseCase,
)
from platform.features.geography.location.location.domain.schemas import (
    CreateCitySchema,
    CreateCountrySchema,
    CreateDepartmentSchema,
    UpdateCitySchema,
    UpdateCountrySchema,
    UpdateDepartmentSchema,
)
from platform.features.geography.location.location.infrastructure.repositories import (
    DjangoGeographyRepository,
)
from platform.features.geography.location.location.presentation.bodies import (
    CreateCityBody,
    CreateCountryBody,
    CreateDepartmentBody,
    UpdateCityBody,
    UpdateCountryBody,
    UpdateDepartmentBody,
)
from platform.features.geography.location.location.presentation.queries import (
    CityListQuery,
    CountryListQuery,
    DepartmentListQuery,
)


def _repo():
    return DjangoGeographyRepository()


def _paginated_response(result):
    dumped = [item.model_dump(mode='json') for item in result.items]
    return wrap_response({
        'items': dumped,
        'total': result.total,
        'page': result.page,
        'page_size': result.page_size,
        'total_pages': result.total_pages,
    })


def _list_response(query, result):
    if query.unpaginated:
        dumped = [item.model_dump(mode='json') for item in result.items]
        return wrap_response(dumped)
    return _paginated_response(result)


# ── Countries ──────────────────────────────────────────────────────────────


class CountryListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CountryListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = ListCountriesUseCase(_repo()).execute(query=query)
        return _list_response(query, result)

    @validated_body(CreateCountryBody)
    def post(self, request, *args, body: dict, **kwargs):
        result = CreateCountryUseCase(_repo()).execute(CreateCountrySchema(**body))
        audit_log(request, 'Country', result.id, 'CREATE', f'Country created: {result.code}')
        return wrap_response(result.model_dump(mode='json'), status_code=201)


class CountryDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetCountryUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateCountryBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        result = UpdateCountryUseCase(_repo()).execute(pk, UpdateCountrySchema(**body))
        audit_log(request, 'Country', pk, 'UPDATE', changes=body)
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, *args, **kwargs):
        DeleteCountryUseCase(_repo()).execute(pk)
        audit_log(request, 'Country', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Departments ────────────────────────────────────────────────────────────


class DepartmentListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(DepartmentListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = ListDepartmentsUseCase(_repo()).execute(query=query)
        return _list_response(query, result)

    @validated_body(CreateDepartmentBody)
    def post(self, request, *args, body: dict, **kwargs):
        result = CreateDepartmentUseCase(_repo()).execute(CreateDepartmentSchema(**body))
        audit_log(
            request, 'Department', result.id, 'CREATE',
            f'Department created: {result.country_code}/{result.code}',
        )
        return wrap_response(result.model_dump(mode='json'), status_code=201)


class DepartmentDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetDepartmentUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateDepartmentBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        result = UpdateDepartmentUseCase(_repo()).execute(pk, UpdateDepartmentSchema(**body))
        audit_log(request, 'Department', pk, 'UPDATE', changes=body)
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, *args, **kwargs):
        DeleteDepartmentUseCase(_repo()).execute(pk)
        audit_log(request, 'Department', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Cities ─────────────────────────────────────────────────────────────────


class CityListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(CityListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = ListCitiesUseCase(_repo()).execute(query=query)
        return _list_response(query, result)

    @validated_body(CreateCityBody)
    def post(self, request, *args, body: dict, **kwargs):
        result = CreateCityUseCase(_repo()).execute(CreateCitySchema(**body))
        audit_log(
            request, 'City', result.id, 'CREATE',
            f'City created: {result.country_code}/{result.department_code}/{result.code}',
        )
        return wrap_response(result.model_dump(mode='json'), status_code=201)


class CityDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetCityUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateCityBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        result = UpdateCityUseCase(_repo()).execute(pk, UpdateCitySchema(**body))
        audit_log(request, 'City', pk, 'UPDATE', changes=body)
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, *args, **kwargs):
        DeleteCityUseCase(_repo()).execute(pk)
        audit_log(request, 'City', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Bulk import ────────────────────────────────────────────────────────────


class LocationImportTemplateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = build_location_import_template()
        response = HttpResponse(result.content, content_type=result.content_type)
        response['Content-Disposition'] = f'attachment; filename="{result.filename}"'
        return response


class LocationImportView(APIView):
    """POST multipart ``file`` → upsert jerárquico de locaciones."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get('file')
        if not upload:
            raise ValidationAppException(
                AppErrorCode.GEO_IMPORT_INVALID_FILE,
                override_detail='Multipart field "file" is required.',
            )
        raw = upload.read()
        if len(raw) > 5 * 1024 * 1024:
            raise ValidationAppException(
                AppErrorCode.GEO_IMPORT_INVALID_FILE,
                override_detail='Import file must be 5 MB or smaller.',
            )
        result = ImportLocationsUseCase(_repo()).execute(
            raw,
            filename=getattr(upload, 'name', '') or 'import.xlsx',
            content_type=getattr(upload, 'content_type', '') or '',
        )
        audit_log(
            request, 'GeographyLocation', 'bulk', 'IMPORT',
            (
                f'countries +{result.created_countries}/~{result.updated_countries} '
                f'depts +{result.created_departments}/~{result.updated_departments} '
                f'cities +{result.created_cities}/~{result.updated_cities} '
                f'skipped={result.skipped}'
            ),
        )
        return wrap_response(result.model_dump(mode='json'))
