"""Build Neurana issue payload from a base commercial invoice + company snapshot."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.conf import settings

from platform.features.billing.commerce.invoice.models import Invoice

# Must match Neurana BillingConcept.code (CreateBillingConceptSchema normalizes '-' → '_').
WA_FISCAL_CONCEPT_CODE = 'WA_SUBSCRIPTION'


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _promo(meta: dict) -> dict:
    nested = meta.get('email_context') if isinstance(meta.get('email_context'), dict) else {}
    return {
        'original_amount': meta.get('original_amount', nested.get('original_amount')),
        'discount_amount': meta.get('discount_amount', nested.get('discount_amount')),
        'description': (
            meta.get('subscription_name')
            or nested.get('subscription_name')
            or f'Subscription invoice'
        ),
    }


def _tax_codes() -> list[str]:
    return [
        str(code).strip().upper()
        for code in (getattr(settings, 'NE_DEFAULT_TAX_CODES', None) or [])
        if str(code).strip()
    ]


def _inclusive_rate() -> Decimal:
    raw = getattr(settings, 'NE_DEFAULT_TAX_RATE', None)
    try:
        rate = Decimal(str(raw if raw is not None else '19'))
    except Exception:
        rate = Decimal('19')
    return rate if rate > 0 else Decimal('0')


def _net_from_inclusive(amount: Decimal, rate: Decimal) -> Decimal:
    """Strip VAT from a tax-inclusive commercial amount so Neurana can re-add it."""
    if rate <= 0 or amount == 0:
        return _money(amount)
    return _money(amount / (Decimal('1') + rate / Decimal('100')))


def build_fiscal_customer(invoice: Invoice, company=None) -> dict[str, Any]:
    tax_id = (invoice.tenant_nit or '').strip()
    legal_name = (invoice.tenant_name or '').strip()
    address = ''
    city_code = ''
    country_code = 'CO'
    external_id = ''
    if company is not None:
        tax_id = tax_id or (getattr(company, 'nit', '') or '').strip()
        legal_name = legal_name or (getattr(company, 'name', '') or '').strip()
        address = (getattr(company, 'address', '') or '').strip()
        company_id = getattr(company, 'id', None)
        if company_id:
            external_id = str(company_id)
        country, _department, city = _company_location(company)
        if city:
            city_code = str(city)[:32]
        if country:
            country_code = str(country)[:2].upper() or 'CO'
    meta = invoice.metadata if isinstance(invoice.metadata, dict) else {}
    email = str(meta.get('recipient_email') or meta.get('customer_email') or '').strip()
    payload = {
        'tax_id': tax_id,
        'tax_id_type': 'NIT',
        'legal_name': legal_name or 'Tenant',
        'email': email,
        'address': address,
        'city_code': city_code,
        'country_code': country_code,
        'phone': '',
    }
    if external_id:
        payload['external_id'] = external_id
    return payload


def _company_location(company) -> tuple[str, str, str]:
    try:
        from platform.features.company.tenant.company.domain.location import company_location_codes

        return company_location_codes(company)
    except Exception:
        return '', '', ''


def build_fiscal_lines(invoice: Invoice) -> list[dict[str, Any]]:
    meta = invoice.metadata if isinstance(invoice.metadata, dict) else {}
    promo = _promo(meta)
    total = Decimal(str(invoice.total_amount or 0))
    original = promo.get('original_amount')
    discount = promo.get('discount_amount')
    unit = Decimal(str(original)) if original is not None else total
    disc = Decimal(str(discount)) if discount is not None else Decimal('0')
    if disc < 0:
        disc = Decimal('0')
    if unit < 0:
        unit = total

    tax_codes = _tax_codes()
    inclusive = bool(getattr(settings, 'NE_TAX_INCLUSIVE', True))
    if tax_codes and inclusive:
        rate = _inclusive_rate()
        unit = _net_from_inclusive(unit, rate)
        disc = _net_from_inclusive(disc, rate)

    description = str(promo.get('description') or f'Subscription invoice {invoice.invoice_number}')
    return [
        {
            'concept_code': WA_FISCAL_CONCEPT_CODE,
            'description': description[:500],
            'quantity': '1',
            'unit_price': str(unit),
            'discount': str(disc),
            'tax_codes': tax_codes,
        },
    ]
