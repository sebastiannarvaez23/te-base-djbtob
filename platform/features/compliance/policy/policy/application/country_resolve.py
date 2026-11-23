"""Resuelve el ISO de política a partir de la empresa del tenant.

Solo duck-typing sobre ``company.geo_city`` (select_related en auth/session).
Sin ORM: Clean Architecture — la presentation/infra carga las relaciones.
"""

from __future__ import annotations

from typing import Optional

from platform.features.compliance.policy.policy.domain.schemas import normalize_country


def resolve_company_policy_country(company) -> Optional[str]:
    """ISO-2 para políticas desde ``company.geo_city`` → departamento → país."""
    if company is None:
        return None
    geo_city = getattr(company, 'geo_city', None)
    if geo_city is None:
        return None
    department = getattr(geo_city, 'department', None)
    country = getattr(department, 'country', None) if department is not None else None
    code = getattr(country, 'code', None) if country is not None else None
    if not code:
        return None
    try:
        return normalize_country(str(code))
    except ValueError:
        return None
