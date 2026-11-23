"""Company location helpers from ``geo_city``."""

from __future__ import annotations

from typing import Any, Tuple

from core.location import (
    entity_location_city_line,
    entity_location_codes,
    entity_location_labels,
)


def company_location_labels(company: Any) -> Tuple[str, str, str]:
    """Return ``(country_name, state_name, city_name)`` from ``geo_city``."""
    return entity_location_labels(company)


def company_location_codes(company: Any) -> Tuple[str, str, str]:
    """Return ``(country_code, department_code, city_code)`` from ``geo_city``."""
    return entity_location_codes(company)


def company_location_city_line(company: Any) -> str:
    """Compact invoice line: ``City, State, Country``."""
    return entity_location_city_line(company)
