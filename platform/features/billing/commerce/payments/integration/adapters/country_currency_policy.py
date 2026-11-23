"""Django adapter — charge currency policy via geography currency catalog."""

from __future__ import annotations

import uuid
from typing import Optional

from django.conf import settings

from core.errors import AppErrorCode, ValidationAppException
from core.trace import trace_layer

from platform.features.billing.commerce.payments.domain.interfaces import ICountryCurrencyPolicy
from platform.features.geography.currency.currency.infrastructure.repositories import (
    DjangoCurrencyRepository,
)


def _fallback_currency() -> str:
    return str(getattr(settings, 'INVOICE_DEFAULT_CURRENCY', 'USD') or 'USD').strip().upper() or 'USD'


def _company_country_code(company_id: uuid.UUID) -> Optional[str]:
    from platform.features.company.tenant.company.domain.location import company_location_codes
    from platform.features.company.tenant.company.models import Company

    try:
        company = (
            Company.objects.select_related('geo_city__department__country')
            .only('id', 'geo_city_id')
            .get(id=company_id)
        )
    except Company.DoesNotExist:
        return None
    country_code, _, _ = company_location_codes(company)
    return (country_code or '').strip().upper() or None


class DjangoCountryCurrencyPolicy(ICountryCurrencyPolicy):
    """Resolves allowed currencies from ``geography_currency`` (repo; Redis via use-case cache optional)."""

    def __init__(self, currency_repo: Optional[DjangoCurrencyRepository] = None):
        self._repo = currency_repo or DjangoCurrencyRepository()

    def _allowed_codes(self, country_code: str) -> list:
        # Infra → repository (not geography application use case) to avoid CA cross-layer hop.
        return self._repo.list_allowed_by_country_code(country_code, active_only=True)

    def _assert_catalog_active(self, code: str) -> str:
        row = self._repo.get_currency_by_code(code)
        if row is None or not row.is_active:
            raise ValidationAppException(AppErrorCode.PAY_CURRENCY_NOT_ALLOWED)
        return code

    @trace_layer('infrastructure')
    def default_currency_for_company(self, company_id: uuid.UUID) -> str:
        country_code = _company_country_code(company_id)
        if not country_code:
            return _fallback_currency()
        try:
            allowed = self._allowed_codes(country_code)
        except Exception:
            return _fallback_currency()
        for item in allowed:
            if item.is_default:
                return item.code.upper()
        if allowed:
            return allowed[0].code.upper()
        # Country exists but no currency links yet — same as missing geo.
        return _fallback_currency()

    @trace_layer('infrastructure')
    def assert_charge_currency(self, *, company_id: uuid.UUID, currency: str) -> str:
        code = (currency or '').strip().upper()
        if not code:
            code = self.default_currency_for_company(company_id)
        country_code = _company_country_code(company_id)
        if not country_code:
            return self._assert_catalog_active(code)
        try:
            allowed = self._allowed_codes(country_code)
        except Exception:
            raise ValidationAppException(AppErrorCode.PAY_CURRENCY_NOT_ALLOWED) from None
        codes = {item.code.upper() for item in allowed}
        if not codes:
            # Empty allow-list: do not brick charges; validate against master catalog.
            return self._assert_catalog_active(code)
        if code not in codes:
            # Preferred (e.g. plan) not allowed — fall back to country default when caller
            # passed an explicit code that is off-policy (renewals with USD plan / COP-only).
            for item in allowed:
                if item.is_default:
                    return item.code.upper()
            return allowed[0].code.upper()
        return code

    @trace_layer('infrastructure')
    def assert_refund_currency(self, *, charge_currency: str, currency: str) -> str:
        charge_code = (charge_currency or '').strip().upper()
        refund_code = (currency or charge_code).strip().upper()
        if not charge_code or refund_code != charge_code:
            raise ValidationAppException(AppErrorCode.PAY_CURRENCY_MISMATCH)
        return refund_code
