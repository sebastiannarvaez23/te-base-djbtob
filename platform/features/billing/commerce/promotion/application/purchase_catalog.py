"""Public gift/discount purchase catalog (pure pricing tables).

Settings / plan loading happen in composition or the use case — not here.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional

from core.errors import AppErrorCode, AppException

from ..domain.schemas import PlanSnapshot

# Monthly list prices (USD) aligned with seed subscriptions: standard/pro/enterprise.
_PURCHASABLE_TIERS: tuple[tuple[str, int], ...] = (
    ('STANDARD', 29),
    ('PRO', 99),
    ('ENTERPRISE', 249),
)
_GIFT_MONTHS: tuple[int, ...] = (1, 3, 6, 12)
_GIFT_MONTH_MULTIPLIERS: dict[int, Decimal] = {
    1: Decimal('1'),
    3: Decimal('3.02'),
    6: Decimal('5.55'),
    12: Decimal('10.1'),
}
_DISCOUNT_PERCENTS: tuple[int, ...] = (10, 20, 30)
_DISCOUNT_DURATIONS: tuple[int, ...] = (1, 3, 6)


def _build_default_catalog() -> dict[str, list[dict[str, Any]]]:
    gift: list[dict[str, Any]] = []
    for code, monthly in _PURCHASABLE_TIERS:
        monthly_dec = Decimal(str(monthly))
        for months in _GIFT_MONTHS:
            gift.append({
                'subscription_code': code,
                'benefit_months': months,
                'price': int((monthly_dec * _GIFT_MONTH_MULTIPLIERS[months]).quantize(Decimal('1'))),
            })

    discount: list[dict[str, Any]] = []
    for code, monthly in _PURCHASABLE_TIERS:
        monthly_dec = Decimal(str(monthly))
        for pct in _DISCOUNT_PERCENTS:
            pct_dec = Decimal(pct) / Decimal('100')
            for duration in _DISCOUNT_DURATIONS:
                amount = monthly_dec * pct_dec * Decimal(duration)
                discount.append({
                    'subscription_code': code,
                    'discount_percent': pct,
                    'discount_duration_months': duration,
                    'price': int(amount.quantize(Decimal('1'))),
                })

    return {'gift': gift, 'discount': discount}


DEFAULT_CATALOG: dict[str, list[dict[str, Any]]] = _build_default_catalog()


@dataclass(frozen=True)
class CatalogMatch:
    subscription_id: uuid.UUID
    subscription_name: str
    subscription_code: str
    amount: Decimal
    currency: str
    description: str


def parse_catalog(raw) -> dict[str, list[dict[str, Any]]]:
    """Pure parser: normalise a raw catalog value into a dict (no settings)."""
    if not raw:
        return DEFAULT_CATALOG
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise AppException(AppErrorCode.PROMO_INTERNAL) from exc


def _gift_purchase_amount(monthly: Decimal, benefit_months: int) -> Decimal:
    multiplier = _GIFT_MONTH_MULTIPLIERS.get(benefit_months)
    if multiplier is None:
        raise AppException(AppErrorCode.PROMO_PLAN_INELIGIBLE)
    return (monthly * multiplier).quantize(Decimal('1'))


def _discount_purchase_amount(
    monthly: Decimal,
    *,
    discount_percent: Decimal,
    discount_duration_months: int,
) -> Decimal:
    pct_dec = discount_percent / Decimal('100')
    return (
        monthly * pct_dec * Decimal(discount_duration_months)
    ).quantize(Decimal('0.01'))


def lookup_gift_price(
    *,
    plan: PlanSnapshot,
    benefit_months: int,
    catalog: Optional[dict] = None,
    currency: str = 'USD',
) -> CatalogMatch:
    gift_rows = (catalog or DEFAULT_CATALOG).get('gift', [])
    for entry in gift_rows:
        if (
            str(entry.get('subscription_code', '')).upper() == plan.code.upper()
            and int(entry.get('benefit_months', 0)) == benefit_months
        ):
            amount = _gift_purchase_amount(Decimal(str(plan.price)), benefit_months)
            return CatalogMatch(
                subscription_id=plan.id,
                subscription_name=plan.name,
                subscription_code=plan.code,
                amount=amount,
                currency=currency,
                description=f'Regalo {plan.name} — {benefit_months} mes(es)',
            )
    raise AppException(AppErrorCode.PROMO_PLAN_INELIGIBLE)


def lookup_discount_price(
    *,
    plan: PlanSnapshot,
    discount_percent: Decimal,
    discount_duration_months: int,
    catalog: Optional[dict] = None,
    currency: str = 'USD',
) -> CatalogMatch:
    discount_rows = (catalog or DEFAULT_CATALOG).get('discount', [])
    pct = Decimal(str(discount_percent))
    for entry in discount_rows:
        if (
            str(entry.get('subscription_code', '')).upper() == plan.code.upper()
            and Decimal(str(entry.get('discount_percent', 0))) == pct
            and int(entry.get('discount_duration_months', 0)) == discount_duration_months
        ):
            amount = _discount_purchase_amount(
                Decimal(str(plan.price)),
                discount_percent=pct,
                discount_duration_months=discount_duration_months,
            )
            return CatalogMatch(
                subscription_id=plan.id,
                subscription_name=plan.name,
                subscription_code=plan.code,
                amount=amount,
                currency=currency,
                description=(
                    f'Descuento {pct}% {plan.name} — '
                    f'{discount_duration_months} renovación(es)'
                ),
            )
    raise AppException(AppErrorCode.PROMO_PLAN_INELIGIBLE)
