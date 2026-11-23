"""Unit tests for assert_active_geo_city."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from platform.features.company.tenant.company.application.geo_city import assert_active_geo_city


@pytest.mark.unit
def test_assert_active_geo_city_not_found():
    with patch(
        'platform.features.geography.location.location.models.City',
    ) as City:
        City.objects.select_related.return_value.filter.return_value.first.return_value = None
        with pytest.raises(NotFoundException) as exc:
            assert_active_geo_city(uuid4())
    assert exc.value.code == AppErrorCode.GEO_CITY_NOT_FOUND


@pytest.mark.unit
def test_assert_active_geo_city_inactive():
    row = SimpleNamespace(
        is_active=False,
        department=SimpleNamespace(is_active=True, country=SimpleNamespace(is_active=True, code='CO')),
    )
    with patch(
        'platform.features.geography.location.location.models.City',
    ) as City:
        City.objects.select_related.return_value.filter.return_value.first.return_value = row
        with pytest.raises(ConflictException) as exc:
            assert_active_geo_city(uuid4())
    assert exc.value.code == AppErrorCode.GEO_CITY_INACTIVE


@pytest.mark.unit
def test_assert_active_geo_city_country_mismatch():
    row = SimpleNamespace(
        is_active=True,
        department=SimpleNamespace(
            is_active=True,
            country=SimpleNamespace(is_active=True, code='CO'),
        ),
    )
    with patch(
        'platform.features.geography.location.location.models.City',
    ) as City:
        City.objects.select_related.return_value.filter.return_value.first.return_value = row
        with pytest.raises(ValidationAppException):
            assert_active_geo_city(uuid4(), expected_country_code='MX')


@pytest.mark.unit
def test_assert_active_geo_city_ok():
    row = SimpleNamespace(
        is_active=True,
        department=SimpleNamespace(
            is_active=True,
            country=SimpleNamespace(is_active=True, code='CO'),
        ),
    )
    with patch(
        'platform.features.geography.location.location.models.City',
    ) as City:
        City.objects.select_related.return_value.filter.return_value.first.return_value = row
        assert_active_geo_city(uuid4(), expected_country_code='CO')
