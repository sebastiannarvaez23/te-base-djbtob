"""Unit tests for public purchase catalog lookup."""

import uuid
from decimal import Decimal

import pytest

from core.errors import AppException

from platform.features.billing.commerce.promotion.application.purchase_catalog import (
    _discount_purchase_amount,
    lookup_discount_price,
    lookup_gift_price,
)
from platform.features.billing.commerce.promotion.domain.schemas import PlanSnapshot

pytestmark = pytest.mark.unit

_CATALOG = {
    'gift': [{'subscription_code': 'PRO', 'benefit_months': 3, 'price': 299}],
    'discount': [{
        'subscription_code': 'PRO',
        'discount_percent': 20,
        'discount_duration_months': 3,
        'price': 149,
    }],
}


def _plan(*, code: str = 'PRO', name: str = 'Pro', price: str = '99') -> PlanSnapshot:
    return PlanSnapshot(id=uuid.uuid4(), code=code, name=name, price=Decimal(price))


@pytest.mark.parametrize(
    'monthly, discount_percent, duration_months, expected',
    [
        (Decimal('399'), Decimal('10'), 1, Decimal('39.90')),
        (Decimal('399'), Decimal('10'), 3, Decimal('119.70')),
        (Decimal('399'), Decimal('10'), 6, Decimal('239.40')),
        (Decimal('399'), Decimal('20'), 3, Decimal('239.40')),
        (Decimal('129'), Decimal('10'), 1, Decimal('12.90')),
        (Decimal('129'), Decimal('20'), 3, Decimal('77.40')),
        (Decimal('99'), Decimal('20'), 3, Decimal('59.40')),
        (Decimal('39'), Decimal('10'), 3, Decimal('11.70')),
    ],
)
def test_discount_purchase_amount_formula(
    monthly, discount_percent, duration_months, expected,
):
    amount = _discount_purchase_amount(
        monthly,
        discount_percent=discount_percent,
        discount_duration_months=duration_months,
    )
    assert amount == expected


def test_lookup_discount_uses_db_price_not_catalog_price():
    plan = _plan(code='PRO', name='Pro', price='129')
    match = lookup_discount_price(
        plan=plan,
        discount_percent=Decimal('20'),
        discount_duration_months=3,
        catalog=_CATALOG,
    )
    assert match.amount == Decimal('77.40')


def test_lookup_discount_scales_with_duration_months():
    plan = _plan(code='enterprise', name='Enterprise', price='399')
    one_month = lookup_discount_price(
        plan=plan, discount_percent=Decimal('10'), discount_duration_months=1, catalog=None,
    )
    three_months = lookup_discount_price(
        plan=plan, discount_percent=Decimal('10'), discount_duration_months=3, catalog=None,
    )
    assert one_month.amount == Decimal('39.90')
    assert three_months.amount == Decimal('119.70')
    assert three_months.amount == one_month.amount * 3


def test_lookup_unknown_discount_combo_raises():
    plan = _plan()
    with pytest.raises(AppException):
        lookup_discount_price(
            plan=plan,
            discount_percent=Decimal('30'),
            discount_duration_months=6,
            catalog=_CATALOG,
        )


def test_lookup_gift_price_by_code():
    plan = _plan()
    match = lookup_gift_price(plan=plan, benefit_months=3, catalog=_CATALOG)
    assert match.amount == Decimal('299')
    assert 'Pro' in match.description


def test_lookup_unknown_combo_raises():
    plan = _plan()
    with pytest.raises(AppException):
        lookup_gift_price(plan=plan, benefit_months=99, catalog=_CATALOG)


def test_default_catalog_supports_standard_gift():
    plan = _plan(code='standard', name='Standard', price='29')
    match = lookup_gift_price(plan=plan, benefit_months=3)
    assert match.amount == Decimal('88')
    assert 'Standard' in match.description


def test_default_catalog_supports_enterprise_discount():
    plan = _plan(code='enterprise', name='Enterprise', price='249')
    match = lookup_discount_price(
        plan=plan, discount_percent=Decimal('20'), discount_duration_months=3,
    )
    assert match.amount == Decimal('149.40')
    assert 'Enterprise' in match.description


def test_lookup_discount_price_is_percent_of_monthly_plan():
    plan = _plan(code='enterprise', name='Enterprise', price='399')
    match = lookup_discount_price(
        plan=plan, discount_percent=Decimal('10'), discount_duration_months=3,
    )
    assert match.amount == Decimal('119.70')
