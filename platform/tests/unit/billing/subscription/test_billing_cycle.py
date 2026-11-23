"""Unit tests for annual vs monthly subscription billing math."""
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase

import pytest

from platform.features.billing.subscription.subscription.domain.billing_cycle import (
    ANNUAL_DISCOUNT_PERCENT,
    MONTHLY,
    YEARLY,
    charge_amount,
    normalize_billing_interval,
    period_delta,
    yearly_amount,
)

pytestmark = pytest.mark.unit


class TestYearlyAmount(TestCase):

    def test_fifteen_percent_off_twelve_months(self):
        self.assertEqual(yearly_amount(Decimal('100.00')), Decimal('1020.00'))
        self.assertEqual(ANNUAL_DISCOUNT_PERCENT, Decimal('15'))

    def test_quantizes_to_cents(self):
        # 29.99 × 12 = 359.88; 15% = 53.982 → 53.98; 359.88 − 53.98 = 305.90
        self.assertEqual(yearly_amount(Decimal('29.99')), Decimal('305.90'))

    def test_zero_and_none_are_zero(self):
        self.assertEqual(yearly_amount(Decimal('0')), Decimal('0.00'))
        self.assertEqual(yearly_amount(None), Decimal('0.00'))

    def test_custom_percent_twenty(self):
        self.assertEqual(yearly_amount(Decimal('100.00'), Decimal('20')), Decimal('960.00'))

    def test_zero_percent_is_full_year(self):
        self.assertEqual(yearly_amount(Decimal('100.00'), Decimal('0')), Decimal('1200.00'))

    def test_unusable_percent_falls_back_to_default(self):
        self.assertEqual(yearly_amount(Decimal('100.00'), 'nope'), Decimal('1020.00'))


class TestChargeAmount(TestCase):

    def test_monthly_is_list_price(self):
        self.assertEqual(charge_amount(Decimal('99.00'), MONTHLY), Decimal('99.00'))

    def test_yearly_applies_annual_discount(self):
        self.assertEqual(charge_amount(Decimal('99.00'), YEARLY), Decimal('1009.80'))

    def test_blank_interval_defaults_to_monthly(self):
        self.assertEqual(charge_amount(Decimal('10.00'), None), Decimal('10.00'))

    def test_invalid_interval_raises(self):
        with self.assertRaises(ValueError):
            charge_amount(Decimal('10.00'), 'weekly')


class TestPeriodDelta(TestCase):

    def test_monthly_is_thirty_days(self):
        self.assertEqual(period_delta(MONTHLY), timedelta(days=30))

    def test_yearly_is_365_days(self):
        self.assertEqual(period_delta(YEARLY), timedelta(days=365))


class TestNormalize(TestCase):

    def test_blank_is_monthly(self):
        self.assertEqual(normalize_billing_interval(None), MONTHLY)
        self.assertEqual(normalize_billing_interval(''), MONTHLY)

    def test_case_insensitive(self):
        self.assertEqual(normalize_billing_interval('YEARLY'), YEARLY)
