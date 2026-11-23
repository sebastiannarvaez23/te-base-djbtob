"""B — ValidateVoucherUseCase unit tests (mocked repository + plan catalog port)."""

from datetime import timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from core.errors import AppErrorCode, ConflictException, NotFoundException
from platform.features.billing.commerce.promotion.application.use_cases import ValidateVoucherUseCase
from platform.tests.unit.billing.promotion.conftest import (
    FakePlanCatalog,
    make_plan_snapshot,
    make_validate_schema,
    make_voucher_schema,
)

pytestmark = pytest.mark.unit


class TestValidateVoucherUseCase(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.repo.has_active_benefit.return_value = False
        self.target = make_plan_snapshot(price='100')

    def _uc(self, current=None):
        return ValidateVoucherUseCase(self.repo, FakePlanCatalog(self.target, current))

    def _voucher(self, **overrides):
        now = timezone.now()
        overrides.setdefault('subscription_ids', [self.target.id])
        overrides.setdefault('redeem_valid_from', now - timedelta(days=1))
        overrides.setdefault('redeem_valid_until', now + timedelta(days=30))
        return make_voucher_schema(**overrides)

    def _schema(self, **kwargs):
        kwargs.setdefault('subscription_id', self.target.id)
        return make_validate_schema(**kwargs)

    def test_b1_1_preview_ok(self):
        self.repo.get_by_serial.return_value = self._voucher(voucher_type='GIFT', benefit_months=3)
        result = self._uc().execute(self._schema())
        self.assertEqual(result.final_amount, Decimal('0'))

    def test_b1_2_not_found(self):
        self.repo.get_by_serial.return_value = None
        with self.assertRaises(NotFoundException):
            self._uc().execute(self._schema(serial='MISSING'))

    def test_b1_17_gift_final_zero(self):
        self.repo.get_by_serial.return_value = self._voucher(voucher_type='GIFT', benefit_months=3)
        result = self._uc().execute(self._schema())
        self.assertEqual(result.original_amount, Decimal('100'))
        self.assertEqual(result.final_amount, Decimal('0'))

    def test_b1_18_discount_twenty_percent(self):
        self.repo.get_by_serial.return_value = self._voucher(
            voucher_type='DISCOUNT',
            benefit_months=None,
            discount_percent=Decimal('20'),
            discount_duration_months=3,
        )
        result = self._uc().execute(self._schema())
        self.assertEqual(result.final_amount, Decimal('80'))

    def test_b1_25_active_benefit(self):
        self.repo.has_active_benefit.return_value = True
        self.repo.get_by_serial.return_value = self._voucher()
        with self.assertRaises(ConflictException) as ctx:
            self._uc().execute(self._schema())
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_BENEFIT_ACTIVE)
