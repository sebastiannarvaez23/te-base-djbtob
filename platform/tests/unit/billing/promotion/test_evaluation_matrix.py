"""Parametrized matrix for critical PROMO_* rules."""

from decimal import Decimal

import pytest

from core.errors import AppErrorCode, AppException
from platform.features.billing.commerce.promotion.application.pricing import apply_discount
from platform.features.billing.commerce.promotion.application.voucher_validator import validate_create_input
from platform.tests.unit.billing.promotion.conftest import make_create_schema

pytestmark = pytest.mark.unit


@pytest.mark.parametrize('percent,expected_final', [
    (Decimal('20'), Decimal('80.00')),
    (Decimal('100'), Decimal('0')),
    (Decimal('0'), Decimal('100')),
])
def test_discount_matrix(percent, expected_final):
    final, _ = apply_discount(Decimal('100'), percent)
    assert final == expected_final


@pytest.mark.parametrize('benefit_months,code', [
    (0, AppErrorCode.PROMO_INVALID_INPUT),
    (37, AppErrorCode.PROMO_INVALID_INPUT),
    (1, None),
    (36, None),
])
def test_gift_benefit_months_bounds(benefit_months, code):
    data = make_create_schema(benefit_months=benefit_months)
    if code is None:
        validate_create_input(data)
    else:
        with pytest.raises(AppException) as exc:
            validate_create_input(data)
        assert exc.value.code == code


@pytest.mark.parametrize('discount,code', [
    (Decimal('0'), AppErrorCode.PROMO_INVALID_INPUT),
    (Decimal('101'), AppErrorCode.PROMO_INVALID_INPUT),
    (Decimal('15'), None),
])
def test_discount_percent_bounds(discount, code):
    data = make_create_schema(
        voucher_type='DISCOUNT',
        discount_percent=discount,
    )
    if code is None:
        validate_create_input(data)
    else:
        with pytest.raises(AppException) as exc:
            validate_create_input(data)
        assert exc.value.code == code
