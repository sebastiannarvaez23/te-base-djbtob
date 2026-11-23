"""A.1 — CreateVoucherUseCase unit tests (mocked repository)."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from core.errors import AppErrorCode, AppException
from platform.features.billing.commerce.promotion.application.use_cases import CreateVoucherUseCase
from platform.features.billing.commerce.promotion.application.voucher_validator import validate_create_input
from platform.tests.unit.billing.promotion.conftest import make_create_schema, make_voucher_schema

pytestmark = pytest.mark.unit


class TestValidateCreateInput(TestCase):

    def test_a1_6_benefit_months_zero(self):
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(benefit_months=0))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)

    def test_a1_7_benefit_months_over_limit(self):
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(benefit_months=37))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)

    def test_a1_8_discount_zero(self):
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(
                voucher_type='DISCOUNT',
                discount_percent=Decimal('0'),
            ))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)

    def test_a1_9_discount_over_100(self):
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(
                voucher_type='DISCOUNT',
                discount_percent=Decimal('101'),
            ))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)

    def test_a1_10_no_plans(self):
        from pydantic import ValidationError
        from platform.features.billing.commerce.promotion.domain.schemas import CreateVoucherSchema
        now = make_create_schema().redeem_valid_from
        with self.assertRaises(ValidationError):
            CreateVoucherSchema(
                voucher_type='GIFT',
                scope='OPEN',
                subscription_ids=[],
                benefit_months=3,
                redeem_valid_from=now,
                redeem_valid_until=now,
            )

    def test_a1_11_inverted_dates(self):
        now = datetime(2026, 7, 1, 12, 0, 0)
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(
                redeem_valid_from=now + timedelta(days=5),
                redeem_valid_until=now,
            ))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)

    def test_a1_14_company_scope_without_company(self):
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(scope='COMPANY', company_id=None))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)

    def test_a1_15_open_with_company_id(self):
        with self.assertRaises(AppException) as ctx:
            validate_create_input(make_create_schema(scope='OPEN', company_id=uuid.uuid4()))
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INVALID_INPUT)


class TestCreateVoucherUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.uc = CreateVoucherUseCase(self.repo)

    def test_a1_1_delegates_to_repository(self):
        expected = make_voucher_schema(serial='WLGX-GFT-ABCD1234', status='ACTIVE')
        self.repo.create.return_value = expected
        data = make_create_schema()
        result = self.uc.execute(data)
        self.repo.create.assert_called_once_with(data)
        self.assertEqual(result.serial, 'WLGX-GFT-ABCD1234')
        self.assertEqual(result.status, 'ACTIVE')

    def test_a1_2_discount_serial(self):
        expected = make_voucher_schema(
            voucher_type='DISCOUNT',
            serial='WLGX-DSC-ABCD1234',
            discount_percent=Decimal('15'),
        )
        self.repo.create.return_value = expected
        result = self.uc.execute(make_create_schema(
            voucher_type='DISCOUNT',
            discount_percent=Decimal('15'),
        ))
        self.assertTrue(result.serial.startswith('WLGX-DSC-'))

    def test_a1_16_notes_persisted_via_repo(self):
        expected = make_voucher_schema(notes='VIP cliente')
        self.repo.create.return_value = expected
        result = self.uc.execute(make_create_schema(notes='VIP cliente'))
        self.assertEqual(result.notes, 'VIP cliente')
