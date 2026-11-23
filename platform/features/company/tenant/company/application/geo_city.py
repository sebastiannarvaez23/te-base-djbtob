"""Validación de ``geo_city`` activa para altas de Company / onboarding."""

from __future__ import annotations

from uuid import UUID

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException


def assert_active_geo_city(
    city_id: UUID,
    *,
    expected_country_code: str | None = None,
) -> None:
    """Exige ciudad activa con departamento y país activos.

    Opcionalmente amarra el ISO del país de la ciudad al ``country_code``
    declarado en onboarding.
    """
    from platform.features.geography.location.location.models import City

    row = (
        City.objects
        .select_related('department', 'department__country')
        .filter(pk=city_id)
        .first()
    )
    if row is None:
        raise NotFoundException(AppErrorCode.GEO_CITY_NOT_FOUND)
    if not row.is_active:
        raise ConflictException(AppErrorCode.GEO_CITY_INACTIVE)
    department = row.department
    if department is None or not department.is_active:
        raise NotFoundException(AppErrorCode.GEO_DEPARTMENT_NOT_FOUND)
    country = department.country
    if country is None or not country.is_active:
        raise ConflictException(AppErrorCode.GEO_COUNTRY_INACTIVE)
    if expected_country_code:
        expected = expected_country_code.strip().upper()
        if country.code != expected:
            raise ValidationAppException(
                AppErrorCode.GEO_CITY_NOT_FOUND,
                override_detail=(
                    'The selected city does not belong to the declared company country.'
                ),
            )
