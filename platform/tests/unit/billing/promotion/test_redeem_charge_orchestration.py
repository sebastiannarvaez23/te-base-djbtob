"""Unit tests: RedeemVoucherUseCase charges SETTINGS paid redeems and rolls back on failure."""

from datetime import timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from django.utils import timezone

from core.errors import AppException
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


class RedeemVoucherUseCaseChargeTests(TestCase):

    def setUp(self):
        self.target = make_plan_snapshot(price='100')

    def _repo(self):
        repo = MagicMock()
        repo.has_active_benefit.return_value = False
        repo.find_redemption_by_idempotency.return_value = None
        now = timezone.now()
        repo.get_by_serial.return_value = make_voucher_schema(
            serial='WLGX-DSC-T1',
            voucher_type='DISCOUNT',
            benefit_months=None,
            discount_percent=Decimal('20'),
            discount_duration_months=1,
            subscription_ids=[self.target.id],
            redeem_valid_from=now - timedelta(days=1),
            redeem_valid_until=now + timedelta(days=30),
        )
        repo.persist_redeem.return_value = make_redeem_result(
            preview={
                'serial': 'WLGX-DSC-T1',
                'voucher_type': 'DISCOUNT',
                'subscription_id': self.target.id,
                'original_amount': Decimal('100'),
                'final_amount': Decimal('80'),
                'discount_amount': Decimal('20'),
            },
        )
        return repo

    def _uc(self, repo, charge):
        return RedeemVoucherUseCase(repo, FakePlanCatalog(self.target), charge)

    def _data(self, **kwargs):
        defaults = dict(
            serial='WLGX-DSC-T1',
            subscription_id=self.target.id,
            company_id=uuid4(),
            context='SETTINGS',
        )
        defaults.update(kwargs)
        return RedeemVoucherSchema(**defaults)

    def test_settings_paid_requires_payment_method(self):
        repo = self._repo()
        uc = self._uc(repo, FakeChargePort())
        with self.assertRaises(AppException):
            uc.execute(self._data())
        repo.persist_redeem.assert_not_called()

    def test_settings_paid_charges_after_redeem(self):
        repo = self._repo()
        charge = FakeChargePort(captured=True)
        uc = self._uc(repo, charge)
        out = uc.execute(self._data(payment_method_id=uuid4()))
        self.assertEqual(out.preview.final_amount, Decimal('80'))
        self.assertEqual(len(charge.calls), 1)
        repo.rollback_redeem.assert_not_called()

    def test_settings_paid_rolls_back_when_charge_fails(self):
        repo = self._repo()
        charge = FakeChargePort(exc=RuntimeError('gateway down'))
        uc = self._uc(repo, charge)
        with self.assertRaises(RuntimeError):
            uc.execute(self._data(payment_method_id=uuid4()))
        repo.rollback_redeem.assert_called_once()
