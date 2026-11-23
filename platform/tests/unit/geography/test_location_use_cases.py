"""Unit tests — maestra geográfica + import CSV/XLSX."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from openpyxl import load_workbook

from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from platform.features.geography.location.location.application.import_use_cases import (
    ImportLocationsUseCase,
)
from platform.features.geography.location.location.application.use_cases import (
    CreateCountryUseCase,
    GetCountryUseCase,
)
from platform.features.geography.location.location.domain.schemas import (
    CountrySchema,
    CreateCountrySchema,
)
from platform.features.geography.location.location.infrastructure.excel_template import (
    build_location_import_template,
)

pytestmark = pytest.mark.unit

SAMPLE_CSV = (
    'country_code,country_name,department_code,department_name,'
    'city_code,city_name,latitude,longitude,is_active\n'
    'CO,Colombia,ANT,Antioquia,MED,Medellín,6.244200,-75.581200,true\n'
    'CO,Colombia,CUN,Cundinamarca,BOG,Bogotá,4.711000,-74.072100,true\n'
)


def _country(**overrides) -> CountrySchema:
    base = dict(
        id=uuid4(),
        code='CO',
        name='Colombia',
        latitude=Decimal('4.570900'),
        longitude=Decimal('-74.297300'),
        is_active=True,
    )
    base.update(overrides)
    return CountrySchema(**base)


class TestCountryUseCases:
    def test_create_country(self):
        repo = MagicMock()
        created = _country()
        repo.create_country.return_value = created
        result = CreateCountryUseCase(repo).execute(
            CreateCountrySchema(code='co', name='Colombia', latitude=Decimal('4.5'), longitude=Decimal('-74.2')),
        )
        assert result.code == 'CO'
        repo.create_country.assert_called_once()

    def test_get_country_not_found(self):
        repo = MagicMock()
        repo.get_country.return_value = None
        with pytest.raises(NotFoundException) as exc:
            GetCountryUseCase(repo).execute(uuid4())
        assert exc.value.code == AppErrorCode.GEO_COUNTRY_NOT_FOUND


class TestImportLocations:
    @patch('platform.features.geography.location.location.application.import_use_cases.transaction.atomic')
    def test_import_hierarchical_csv(self, atomic):
        atomic.return_value.__enter__ = MagicMock(return_value=None)
        atomic.return_value.__exit__ = MagicMock(return_value=False)
        repo = MagicMock()
        country = _country()
        dept_id = uuid4()
        city_id = uuid4()
        repo.upsert_country_by_code.return_value = (country, True)
        repo.upsert_department.return_value = (
            MagicMock(id=dept_id, code='ANT'), True,
        )
        repo.upsert_city.return_value = (
            MagicMock(id=city_id, code='MED'), True,
        )

        result = ImportLocationsUseCase(repo).execute(
            SAMPLE_CSV.encode('utf-8'),
            filename='locations.csv',
            content_type='text/csv',
        )
        assert result.created_countries >= 1
        assert result.created_departments >= 1
        assert result.created_cities >= 1
        assert result.errors == []

    @patch('platform.features.geography.location.location.application.import_use_cases.transaction.atomic')
    def test_import_hierarchical_xlsx(self, atomic):
        atomic.return_value.__enter__ = MagicMock(return_value=None)
        atomic.return_value.__exit__ = MagicMock(return_value=False)
        repo = MagicMock()
        country = _country()
        repo.upsert_country_by_code.return_value = (country, True)
        repo.upsert_department.return_value = (MagicMock(id=uuid4(), code='ANT'), True)
        repo.upsert_city.return_value = (MagicMock(id=uuid4(), code='MED'), True)

        template = build_location_import_template()
        result = ImportLocationsUseCase(repo).execute(
            template.content,
            filename=template.filename,
            content_type=template.content_type,
        )
        assert result.created_countries >= 1
        assert result.created_departments >= 1
        assert result.created_cities >= 1
        assert result.errors == []

    def test_import_rejects_empty(self):
        repo = MagicMock()
        with pytest.raises(ValidationAppException) as exc:
            ImportLocationsUseCase(repo).execute(b'')
        assert exc.value.code == AppErrorCode.GEO_IMPORT_INVALID_FILE

    def test_xlsx_template_headers(self):
        template = build_location_import_template()
        assert template.filename.endswith('.xlsx')
        wb = load_workbook(filename=__import__('io').BytesIO(template.content), read_only=True)
        ws = wb.active
        headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        wb.close()
        assert headers[0] == 'country_code'
        assert headers[1] == 'country_name'
