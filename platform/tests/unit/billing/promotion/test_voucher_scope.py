"""C5 / A1.4 — Voucher scope validation rules."""

import uuid
from unittest import TestCase

import pytest

from core.errors import AppErrorCode, AppException
from platform.features.billing.commerce.promotion.application.voucher_validator import validate_create_input
from platform.tests.unit.billing.promotion.conftest import make_create_schema

pytestmark = pytest.mark.unit


class TestVoucherScope(TestCase):

    def test_a1_4_first_take_without_company(self):
        data = make_create_schema(
            voucher_type='DISCOUNT',
            scope='FIRST_TAKE',
            company_id=None,
            discount_percent=__import__('decimal').Decimal('50'),
        )
        validate_create_input(data)  # must not raise

    def test_c5_open_scope_valid(self):
        validate_create_input(make_create_schema(scope='OPEN', company_id=None))

    def test_company_scope_requires_company_id(self):
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(scope='COMPANY'))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)

    def test_first_take_rejects_company_id(self):
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(
                scope='FIRST_TAKE',
                company_id=uuid.uuid4(),
                voucher_type='DISCOUNT',
                discount_percent=__import__('decimal').Decimal('10'),
            ))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)
