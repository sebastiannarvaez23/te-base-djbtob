"""D4 — pricing.py unit tests."""

from decimal import Decimal
from unittest import TestCase

import pytest

from platform.features.billing.commerce.promotion.application.pricing import (
    apply_discount,
    gift_final_amount,
)

pytestmark = pytest.mark.unit


class TestApplyDiscount(TestCase):

    def test_d4_1_twenty_percent_off_100(self):
        final, discount = apply_discount(Decimal('100'), Decimal('20'))
        self.assertEqual(final, Decimal('80.00'))
        self.assertEqual(discount, Decimal('20.00'))

    def test_d4_2_bankers_rounding_99_33pct(self):
        final, discount = apply_discount(Decimal('99'), Decimal('33'))
        self.assertEqual(discount, Decimal('32.67'))
        self.assertEqual(final, Decimal('66.33'))

    def test_d4_3_zero_price(self):
        final, discount = apply_discount(Decimal('0'), Decimal('20'))
        self.assertEqual(final, Decimal('0'))
        self.assertEqual(discount, Decimal('0'))

    def test_d4_4_hundred_percent(self):
        final, discount = apply_discount(Decimal('50'), Decimal('100'))
        self.assertEqual(final, Decimal('0'))
        self.assertEqual(discount, Decimal('50'))

    def test_d4_5_decimal_percent(self):
        final, discount = apply_discount(Decimal('100'), Decimal('33.33'))
        self.assertEqual(discount, Decimal('33.33'))
        self.assertEqual(final, Decimal('66.67'))


class TestGiftFinalAmount(TestCase):

    def test_gift_zeros_out_price(self):
        final, discount = gift_final_amount(Decimal('100'))
        self.assertEqual(final, Decimal('0'))
        self.assertEqual(discount, Decimal('100'))
