"""Carga masiva CSV/XLSX de países / departamentos / ciudades."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

from django.db import transaction

from core.errors import AppErrorCode, ValidationAppException
from core.importing.file_parsers import ImportFileParserRegistry

from ..domain.interfaces import IGeographyRepository
from ..domain.schemas import (
    CreateCountrySchema,
    LocationImportResultSchema,
    LocationImportRowError,
    normalize_country_code,
    normalize_location_code,
    normalize_name,
)
from core.trace import trace_layer

TEMPLATE_HEADERS = (
    'country_code',
    'country_name',
    'department_code',
    'department_name',
    'city_code',
    'city_name',
    'latitude',
    'longitude',
    'is_active',
)


def _parse_bool(raw: str, default: bool = True) -> bool:
    value = (raw or '').strip().lower()
    if not value:
        return default
    if value in ('1', 'true', 'yes', 'y', 'si', 'sí'):
        return True
    if value in ('0', 'false', 'no', 'n'):
        return False
    raise ValueError('is_active must be true/false')


def _parse_coord(raw: str) -> Optional[Decimal]:
    value = (raw or '').strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('invalid coordinate') from exc


class ImportLocationsUseCase:
    """
    Upsert jerárquico desde CSV o XLSX.

    Cada fila puede crear/actualizar:
    - solo país (department/city vacíos)
    - país + departamento
    - país + departamento + ciudad

    ``latitude`` / ``longitude`` aplican al nivel más profundo presente.
    """

    def __init__(
        self,
        repository: IGeographyRepository,
        *,
        parser_registry: Optional[ImportFileParserRegistry] = None,
    ):
        self.repository = repository
        self._parsers = parser_registry or ImportFileParserRegistry(
            file_invalid_code=AppErrorCode.GEO_IMPORT_INVALID_FILE,
            empty_code=AppErrorCode.GEO_IMPORT_INVALID_FILE,
        )

    @trace_layer('application')
    def execute(
        self,
        file_bytes: bytes,
        *,
        filename: str = 'import.xlsx',
        content_type: str = '',
    ) -> LocationImportResultSchema:
        if not file_bytes:
            raise ValidationAppException(AppErrorCode.GEO_IMPORT_INVALID_FILE)

        parser = self._parsers.resolve(filename, content_type)
        headers, rows = parser.parse(file_bytes)

        required = {'country_code', 'country_name'}
        header_set = {h for h in headers if h}
        if not required.issubset(header_set):
            raise ValidationAppException(
                AppErrorCode.GEO_IMPORT_INVALID_FILE,
                override_detail='File must include country_code and country_name columns.',
            )

        result = LocationImportResultSchema()

        with transaction.atomic():
            for index, row in rows:
                try:
                    self._process_row(row, result)
                except ValueError as exc:
                    result.errors.append(LocationImportRowError(
                        row=index,
                        field='',
                        code=AppErrorCode.GEO_IMPORT_ROW_INVALID.value,
                        detail=str(exc),
                    ))
                    result.skipped += 1
                except Exception as exc:  # noqa: BLE001 — row isolation
                    result.errors.append(LocationImportRowError(
                        row=index,
                        field='',
                        code=AppErrorCode.GEO_IMPORT_ROW_INVALID.value,
                        detail=str(exc),
                    ))
                    result.skipped += 1

        return result

    def _process_row(self, row: dict, result: LocationImportResultSchema) -> None:
        country_code = normalize_country_code(row.get('country_code', ''))
        country_name = normalize_name(row.get('country_name', ''))
        dept_code_raw = row.get('department_code', '')
        city_code_raw = row.get('city_code', '')
        is_active = _parse_bool(row.get('is_active', ''), default=True)
        lat = _parse_coord(row.get('latitude', ''))
        lng = _parse_coord(row.get('longitude', ''))

        country_lat = lat if not dept_code_raw and not city_code_raw else None
        country_lng = lng if not dept_code_raw and not city_code_raw else None
        if dept_code_raw and not city_code_raw:
            dept_lat, dept_lng = lat, lng
            city_lat = city_lng = None
        elif city_code_raw:
            dept_lat = dept_lng = None
            city_lat, city_lng = lat, lng
        else:
            dept_lat = dept_lng = city_lat = city_lng = None

        country, created = self.repository.upsert_country_by_code(
            CreateCountrySchema(
                code=country_code,
                name=country_name,
                latitude=country_lat,
                longitude=country_lng,
                is_active=is_active if not dept_code_raw else True,
            ),
        )
        if created:
            result.created_countries += 1
        else:
            result.updated_countries += 1

        if not dept_code_raw:
            return

        dept_code = normalize_location_code(dept_code_raw)
        dept_name = normalize_name(row.get('department_name', '') or dept_code)
        department, created = self.repository.upsert_department(
            country_id=country.id,
            code=dept_code,
            name=dept_name,
            latitude=dept_lat,
            longitude=dept_lng,
            is_active=is_active if not city_code_raw else True,
        )
        if created:
            result.created_departments += 1
        else:
            result.updated_departments += 1

        if not city_code_raw:
            return

        city_code = normalize_location_code(city_code_raw)
        city_name = normalize_name(row.get('city_name', '') or city_code)
        _, created = self.repository.upsert_city(
            department_id=department.id,
            code=city_code,
            name=city_name,
            latitude=city_lat,
            longitude=city_lng,
            is_active=is_active,
        )
        if created:
            result.created_cities += 1
        else:
            result.updated_cities += 1
