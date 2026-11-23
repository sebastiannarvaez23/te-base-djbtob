"""Unit tests for geography delete conflict mapping."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, ConflictException, NotFoundException
from platform.features.geography.location.location.application.use_cases import (
    DeleteCityUseCase,
    DeleteCountryUseCase,
    DeleteDepartmentUseCase,
)


@pytest.mark.unit
def test_delete_city_maps_in_use():
    repo = MagicMock()
    repo.delete_city.side_effect = ConflictException(AppErrorCode.GEO_CITY_IN_USE)
    with pytest.raises(ConflictException) as exc:
        DeleteCityUseCase(repo).execute(uuid4())
    assert exc.value.code == AppErrorCode.GEO_CITY_IN_USE


@pytest.mark.unit
def test_delete_city_not_found():
    repo = MagicMock()
    repo.delete_city.return_value = False
    with pytest.raises(NotFoundException) as exc:
        DeleteCityUseCase(repo).execute(uuid4())
    assert exc.value.code == AppErrorCode.GEO_CITY_NOT_FOUND


@pytest.mark.unit
def test_delete_country_maps_in_use():
    repo = MagicMock()
    repo.delete_country.side_effect = ConflictException(AppErrorCode.GEO_COUNTRY_IN_USE)
    with pytest.raises(ConflictException) as exc:
        DeleteCountryUseCase(repo).execute(uuid4())
    assert exc.value.code == AppErrorCode.GEO_COUNTRY_IN_USE


@pytest.mark.unit
def test_delete_department_maps_in_use():
    repo = MagicMock()
    repo.delete_department.side_effect = ConflictException(AppErrorCode.GEO_DEPARTMENT_IN_USE)
    with pytest.raises(ConflictException) as exc:
        DeleteDepartmentUseCase(repo).execute(uuid4())
    assert exc.value.code == AppErrorCode.GEO_DEPARTMENT_IN_USE
