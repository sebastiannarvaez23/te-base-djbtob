"""Serial generator unit tests."""

import re
from unittest import TestCase

import pytest

from platform.features.billing.commerce.promotion.application.serial_generator import (
    generate_voucher_serial,
)

pytestmark = pytest.mark.unit

_SERIAL_RE = re.compile(r'^WLGX-(GFT|DSC)-[A-Z0-9]{8}$')


class TestSerialGenerator(TestCase):

    def test_gift_prefix(self):
        serial = generate_voucher_serial('GIFT')
        self.assertTrue(serial.startswith('WLGX-GFT-'))
        self.assertRegex(serial, _SERIAL_RE)

    def test_discount_prefix(self):
        serial = generate_voucher_serial('DISCOUNT')
        self.assertTrue(serial.startswith('WLGX-DSC-'))
        self.assertRegex(serial, _SERIAL_RE)

    def test_uniqueness_across_calls(self):
        serials = {generate_voucher_serial('GIFT') for _ in range(20)}
        self.assertEqual(len(serials), 20)
