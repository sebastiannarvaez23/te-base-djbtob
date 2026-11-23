"""Best-effort registration of a billable company in the Neurana fiscal master.

The company save must succeed even when Neurana is down. The next invoice
upsert covers the gap. This is not a second outbox.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger('app.company')


def register_company_customer(
    company_id,
    *,
    loader: Callable | None = None,
    client_factory: Callable | None = None,
) -> None:
    try:
        company = (loader or _load_company)(company_id)
        if company is None:
            return
        payload = _payload(company)
        if payload is None:
            return
        client = (client_factory or _client)()
        client.register_customer(payload)
    except Exception:
        logger.warning('neurana customer register skipped company_id=%s', company_id, exc_info=True)


def _load_company(company_id):
    from platform.features.company.tenant.company.models import Company

    return (
        Company.objects
        .select_related('geo_city__department__country')
        .filter(pk=company_id)
        .first()
    )


def _client():
    from platform.features.billing.commerce.invoice.infrastructure.fiscal.ecosystem_client import (
        get_ecosystem_client,
    )

    return get_ecosystem_client()


def _payload(company: Any):
    from necore.ecosystem.contracts import RegisterCustomerV1

    from platform.features.company.tenant.company.domain.location import company_location_codes

    nit = (getattr(company, 'nit', '') or '').strip()
    if not nit:
        return None
    country, _department, city = company_location_codes(company)
    country_code = (country or 'CO')[:2].upper() or 'CO'
    legal_name = (getattr(company, 'name', '') or '').strip() or nit
    return RegisterCustomerV1(
        tax_id=nit[:64],
        tax_id_type='NIT',
        legal_name=legal_name[:255],
        address=((getattr(company, 'address', '') or '').strip())[:500],
        city_code=(city or '')[:32],
        country_code=country_code,
        external_id=str(company.id),
    )
