"""Read base prices from the Neurana catalog (source of truth)."""
from __future__ import annotations

import logging
import threading
import time
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.utils import timezone

from core.errors import AppErrorCode, ValidationAppException
from platform.features.billing.subscription.subscription.domain.schemas import SubscriptionSchema
from platform.features.billing.subscription.subscription.models import Subscription

logger = logging.getLogger('billing.subscription.catalog')

_CATALOG_PATH = '/api/v1/ecosystem/catalog/services/'
_CACHE_SECONDS = 30.0
_MONEY = Decimal('0.01')
_PRICE_MAX = Decimal('999999999999.99')

_lock = threading.Lock()
_cached_service_at: dict[str, float] = {}
_cached_service: dict[str, dict] = {}


def fetch_catalog_page(
    *,
    page: int = 0,
    page_size: int = 10,
    q: str = '',
    is_active: Optional[bool] = None,
    service_id: str = '',
) -> Optional[dict]:
    """One Neurana page. ``None`` when the catalog cannot be read."""
    params = {'page': str(page), 'page_size': str(page_size)}
    text = str(q or '').strip()
    if text:
        params['q'] = text
    if is_active is not None:
        params['is_active'] = 'true' if is_active else 'false'
    if service_id:
        params['id'] = str(service_id)
    try:
        from platform.features.billing.commerce.invoice.infrastructure.fiscal.ecosystem_client import (
            get_ecosystem_client,
        )

        raw = get_ecosystem_client().request('GET', _CATALOG_PATH, params=params)
    except Exception:
        logger.warning('neurana catalog services unavailable', exc_info=True)
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get('items'), list):
        return None
    items = [row for row in raw['items'] if isinstance(row, dict) and row.get('id')]
    try:
        total = int(raw.get('total') or 0)
        total_pages = int(raw.get('total_pages') or 0)
    except (TypeError, ValueError):
        total = len(items)
        total_pages = 1 if items else 0
    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
    }


def fetch_service(service_id) -> Optional[dict]:
    """One service, ``{}`` when it is not in this product, ``None`` on outage."""
    wanted = str(service_id)
    now = time.monotonic()
    with _lock:
        cached_at = _cached_service_at.get(wanted)
        if cached_at is not None and (now - cached_at) < _CACHE_SECONDS:
            return dict(_cached_service.get(wanted) or {})
    page = fetch_catalog_page(page=0, page_size=1, service_id=wanted)
    if page is None:
        return None
    match = next((row for row in page['items'] if str(row.get('id')) == wanted), None)
    stored = dict(match or {})
    with _lock:
        _cached_service_at[wanted] = time.monotonic()
        _cached_service[wanted] = stored
    return dict(stored)


def reset_catalog_cache() -> None:
    with _lock:
        _cached_service_at.clear()
        _cached_service.clear()


def require_active_service(service_id) -> dict:
    """Return the catalog service or raise a billing error the admin can act on."""
    match = fetch_service(service_id)
    if match is None:
        raise ValidationAppException(AppErrorCode.SUB_CATALOG_UNAVAILABLE)
    if not match or not match.get('is_active', True):
        raise ValidationAppException(AppErrorCode.SUB_CATALOG_SERVICE)
    price = _money(match.get('min_billing_base'))
    currency = str(match.get('currency') or '').strip().upper()
    if price is None or len(currency) != 3 or not currency.isalpha():
        raise ValidationAppException(AppErrorCode.SUB_CATALOG_SERVICE)
    match = dict(match)
    match['min_billing_base'] = price
    match['currency'] = currency
    return match


def _money(value) -> Optional[Decimal]:
    try:
        amount = Decimal(str(value)).quantize(_MONEY)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if amount < 0 or amount > _PRICE_MAX:
        return None
    return amount


def _persist(plans: list[SubscriptionSchema]) -> None:
    now = timezone.now()
    for plan in plans:
        if plan.id is None:
            continue
        Subscription.objects.filter(pk=plan.id).update(
            price=plan.price,
            currency=plan.currency,
            catalog_service_code=plan.catalog_service_code,
            catalog_service_name=plan.catalog_service_name,
            updated_at=now,
        )


def overlay_catalog_prices(plans: list[SubscriptionSchema]) -> list[SubscriptionSchema]:
    """Replace linked plan prices with the live catalog amount and store the snapshot."""
    if not any(plan.catalog_service_id for plan in plans):
        return plans
    changed: list[SubscriptionSchema] = []
    updated: list[SubscriptionSchema] = []
    for plan in plans:
        service_id = plan.catalog_service_id
        row = fetch_service(service_id) if service_id else {}
        if not row:
            updated.append(plan)
            continue
        price = _money(row.get('min_billing_base'))
        currency = str(row.get('currency') or '').strip().upper()
        if price is None or len(currency) != 3 or not currency.isalpha():
            updated.append(plan)
            continue
        code = str(row.get('code') or '')[:64]
        name = str(row.get('name') or '')[:255]
        if (
            plan.price == price
            and plan.currency == currency
            and plan.catalog_service_code == code
            and plan.catalog_service_name == name
        ):
            updated.append(plan)
            continue
        plan = plan.model_copy(update={
            'price': price,
            'currency': currency,
            'catalog_service_code': code,
            'catalog_service_name': name,
        })
        changed.append(plan)
        updated.append(plan)
    if changed:
        try:
            _persist(changed)
        except Exception:
            logger.exception('could not store catalog price snapshot')
    return updated
