"""D3 — unit tests for automatic renewal + active promotion benefits.

Covers get_renewal_charge_amount / after_successful_renewal_charge without DB via
the repository port: discount reduces the charge, gift skips it, exhausted cycles
fall back to full price.
"""
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from platform.features.billing.commerce.promotion.application.renewal_integration import (
    after_successful_renewal_charge,
    get_renewal_charge_amount,
)
from platform.features.billing.commerce.promotion.domain.schemas import ActiveBenefitSchema

pytestmark = pytest.mark.unit


def _benefit(
    *,
    voucher_type: str,
    discount_percent=None,
    remaining_discount_cycles=None,
    benefit_end=None,
    serial='WLGX-DSC-TEST01',
) -> ActiveBenefitSchema:
    now = timezone.now()
    return ActiveBenefitSchema(
        id=uuid.uuid4(),
        voucher_type=voucher_type,
        voucher_serial=serial,
        subscription_id=uuid.uuid4(),
        subscription_name='Pro',
        benefit_start=now - timedelta(days=1),
        benefit_end=benefit_end or (now + timedelta(days=30)),
        discount_percent=discount_percent,
        remaining_discount_cycles=remaining_discount_cycles,
        status='ACTIVE',
    )


def _repo(benefit):
    repo = MagicMock()
    repo.get_active_benefit.return_value = benefit
    return repo


class TestGetRenewalChargeAmount(TestCase):

    def test_d3_no_active_benefit_charges_full_price(self):
        amount, meta, skip = get_renewal_charge_amount(_repo(None), uuid.uuid4(), Decimal('100.00'))
        self.assertEqual(amount, Decimal('100.00'))
        self.assertEqual(meta, {})
        self.assertFalse(skip)

    def test_d3_1_active_discount_reduces_renewal_amount(self):
        benefit = _benefit(
            voucher_type='DISCOUNT',
            discount_percent=Decimal('20'),
            remaining_discount_cycles=3,
            serial='WLGX-DSC-RNW001',
        )
        amount, meta, skip = get_renewal_charge_amount(_repo(benefit), uuid.uuid4(), Decimal('100.00'))

        self.assertFalse(skip)
        self.assertEqual(amount, Decimal('80.00'))
        self.assertEqual(meta['voucher_type'], 'DISCOUNT')
        self.assertEqual(meta['promotion_serial'], 'WLGX-DSC-RNW001')
        self.assertEqual(meta['original_amount'], '100.00')
        self.assertEqual(meta['discount_amount'], '20.00')
        self.assertEqual(meta['email_context']['promotion_voucher_type'], 'DISCOUNT')
        self.assertEqual(meta['email_context']['promotion_discount_amount'], 20.0)

    def test_d3_1_discount_applies_to_plan_price_not_flat(self):
        benefit = _benefit(
            voucher_type='DISCOUNT',
            discount_percent=Decimal('20'),
            remaining_discount_cycles=1,
        )
        amount, meta, skip = get_renewal_charge_amount(_repo(benefit), uuid.uuid4(), Decimal('399.00'))

        self.assertFalse(skip)
        self.assertEqual(amount, Decimal('319.20'))
        self.assertEqual(meta['discount_amount'], '79.80')

    def test_d3_3_exhausted_discount_cycles_charges_full_price(self):
        benefit = _benefit(
            voucher_type='DISCOUNT',
            discount_percent=Decimal('20'),
            remaining_discount_cycles=0,
        )
        amount, meta, skip = get_renewal_charge_amount(_repo(benefit), uuid.uuid4(), Decimal('100.00'))

        self.assertEqual(amount, Decimal('100.00'))
        self.assertEqual(meta, {})
        self.assertFalse(skip)

    def test_d3_discount_without_percent_charges_full_price(self):
        benefit = _benefit(
            voucher_type='DISCOUNT',
            discount_percent=None,
            remaining_discount_cycles=2,
        )
        amount, meta, skip = get_renewal_charge_amount(_repo(benefit), uuid.uuid4(), Decimal('100.00'))

        self.assertEqual(amount, Decimal('100.00'))
        self.assertFalse(skip)

    def test_active_gift_skips_charge(self):
        benefit = _benefit(
            voucher_type='GIFT',
            serial='WLGX-GFT-RNW001',
            benefit_end=timezone.now() + timedelta(days=10),
        )
        amount, meta, skip = get_renewal_charge_amount(_repo(benefit), uuid.uuid4(), Decimal('100.00'))

        self.assertTrue(skip)
        self.assertEqual(amount, Decimal('0'))
        self.assertEqual(meta['voucher_type'], 'GIFT')
        self.assertEqual(meta['promotion_serial'], 'WLGX-GFT-RNW001')
        self.assertEqual(meta['discount_amount'], '100.00')

    def test_expired_gift_does_not_skip_charge(self):
        benefit = _benefit(
            voucher_type='GIFT',
            benefit_end=timezone.now() - timedelta(days=1),
        )
        amount, meta, skip = get_renewal_charge_amount(_repo(benefit), uuid.uuid4(), Decimal('100.00'))

        self.assertFalse(skip)
        self.assertEqual(amount, Decimal('100.00'))
        self.assertEqual(meta, {})


class TestAfterSuccessfulRenewalCharge(TestCase):

    def test_d3_2_decrements_remaining_discount_cycles(self):
        benefit = _benefit(
            voucher_type='DISCOUNT',
            discount_percent=Decimal('20'),
            remaining_discount_cycles=3,
        )
        repo = _repo(benefit)
        after_successful_renewal_charge(repo, uuid.uuid4())
        repo.decrement_discount_cycle.assert_called_once_with(benefit.id)

    def test_gift_does_not_decrement_cycles(self):
        repo = _repo(_benefit(voucher_type='GIFT'))
        after_successful_renewal_charge(repo, uuid.uuid4())
        repo.decrement_discount_cycle.assert_not_called()

    def test_no_active_benefit_is_noop(self):
        repo = _repo(None)
        after_successful_renewal_charge(repo, uuid.uuid4())
        repo.decrement_discount_cycle.assert_not_called()
