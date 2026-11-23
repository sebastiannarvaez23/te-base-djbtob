"""D — Discount redemption use case unit tests (ports)."""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from core.errors import AppErrorCode, ConflictException
from platform.features.billing.commerce.promotion.application.use_cases import RedeemVoucherUseCase
from platform.features.billing.commerce.promotion.domain.schemas import RedeemVoucherSchema
from platform.tests.unit.billing.promotion.conftest import (
    FakeChargePort,
    FakePlanCatalog,
    make_plan_snapshot,
    make_redeem_result,
    make_voucher_schema,
)

pytestmark = pytest.mark.unit


class TestRedeemVoucherDiscount(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.repo.has_active_benefit.return_value = False
        self.repo.find_redemption_by_idempotency.return_value = None
        self.target = make_plan_snapshot(price='100')

    def _uc(self, current=None, charge=None):
        return RedeemVoucherUseCase(
            self.repo, FakePlanCatalog(self.target, current), charge or FakeChargePort(),
        )

    def _voucher(self, **overrides):
        now = timezone.now()
        overrides.setdefault('subscription_ids', [self.target.id])
        overrides.setdefault('redeem_valid_from', now - timedelta(days=1))
        overrides.setdefault('redeem_valid_until', now + timedelta(days=30))
        overrides.setdefault('voucher_type', 'DISCOUNT')
        overrides.setdefault('benefit_months', None)
        return make_voucher_schema(**overrides)

    def _redeem(self, **kwargs):
        defaults = dict(
            serial='WLGX-DSC-TEST0001',
            subscription_id=self.target.id,
            company_id=uuid.uuid4(),
            context='SETTINGS',
        )
        defaults.update(kwargs)
        return RedeemVoucherSchema(**defaults)

    def test_d1_1_twenty_percent_onboarding(self):
        self.repo.get_by_serial.return_value = self._voucher(
            discount_percent=Decimal('20'), discount_duration_months=3,
        )
        self.repo.persist_redeem.return_value = make_redeem_result(
            redemption={'context': 'ONBOARDING'},
            preview={
                'voucher_type': 'DISCOUNT',
                'original_amount': Decimal('100'),
                'final_amount': Decimal('80'),
                'discount_amount': Decimal('20'),
                'discount_percent': Decimal('20'),
            },
        )
        out = self._uc().execute(self._redeem(context='ONBOARDING'))
        self.assertEqual(out.preview.final_amount, Decimal('80'))

    def test_d1_4_hundred_percent_no_charge(self):
        self.repo.get_by_serial.return_value = self._voucher(
            discount_percent=Decimal('100'), discount_duration_months=1,
        )
        self.repo.persist_redeem.return_value = make_redeem_result(
            preview={
                'voucher_type': 'DISCOUNT',
                'final_amount': Decimal('0'),
                'discount_percent': Decimal('100'),
            },
        )
        out = self._uc().execute(self._redeem())
        self.assertEqual(out.preview.final_amount, Decimal('0'))

    def test_d2_4_active_discount_blocks_another(self):
        self.repo.has_active_benefit.return_value = True
        self.repo.get_by_serial.return_value = self._voucher(discount_percent=Decimal('20'))
        with self.assertRaises(ConflictException) as ctx:
            self._uc().execute(self._redeem())
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_BENEFIT_ACTIVE)
