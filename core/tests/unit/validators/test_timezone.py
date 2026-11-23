"""IANA timezone helper used by preference bodies."""

from unittest import TestCase

from core.validators import ValidationCode
from core.validators.timezone import (
    DATE_FORMAT_CHOICES,
    TIME_FORMAT_CHOICES,
    coerce_date_format,
    coerce_optional_date_format,
    coerce_optional_time_format,
    coerce_time_format,
    iana_timezone_errors,
)

import pytest

pytestmark = pytest.mark.unit


class TestIanaTimezoneErrors(TestCase):

    def test_empty_is_ok(self):
        self.assertEqual(iana_timezone_errors(None), [])
        self.assertEqual(iana_timezone_errors(''), [])

    def test_known_zone(self):
        self.assertEqual(iana_timezone_errors('America/Bogota'), [])
        self.assertEqual(iana_timezone_errors('UTC'), [])
        self.assertEqual(iana_timezone_errors('America/Argentina/Buenos_Aires'), [])

    def test_unknown_zone(self):
        errors = iana_timezone_errors('Not/AZone')
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, 'timezone')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_CHOICE)

    def test_date_format_choices_match_ui(self):
        self.assertEqual(
            DATE_FORMAT_CHOICES,
            ('DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD'),
        )

    def test_time_format_choices_match_ui(self):
        self.assertEqual(TIME_FORMAT_CHOICES, ('12', '24'))


class TestCoerceTimeFormat(TestCase):

    def test_accepts_clock_strings(self):
        self.assertEqual(coerce_time_format('12'), '12')
        self.assertEqual(coerce_time_format('24'), '24')
        self.assertEqual(coerce_time_format(' 12 '), '12')

    def test_coerces_json_numbers(self):
        self.assertEqual(coerce_time_format(12), '12')
        self.assertEqual(coerce_time_format(24), '24')

    def test_rejects_unknown_values(self):
        for value in ('36', 36, 'am', True, None, 12.0):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    coerce_time_format(value)

    def test_optional_none_passthrough(self):
        self.assertIsNone(coerce_optional_time_format(None))
        self.assertEqual(coerce_optional_time_format(12), '12')


class TestCoerceDateFormat(TestCase):

    def test_accepts_catalog_masks(self):
        for mask in DATE_FORMAT_CHOICES:
            with self.subTest(mask=mask):
                self.assertEqual(coerce_date_format(mask), mask)
        self.assertEqual(coerce_date_format(' DD/MM/YYYY '), 'DD/MM/YYYY')

    def test_rejects_unknown_values(self):
        for value in ('dd/mm/yyyy', 'YY-MM-DD', 'YYYY/MM/DD', 12, None, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    coerce_date_format(value)

    def test_optional_none_passthrough(self):
        self.assertIsNone(coerce_optional_date_format(None))
        self.assertEqual(coerce_optional_date_format('YYYY-MM-DD'), 'YYYY-MM-DD')
