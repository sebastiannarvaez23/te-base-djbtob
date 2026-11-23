"""Presentation validation for PATCH /identity/preferences/ (admin)."""

from unittest import TestCase

from core.validators import ValidationCode
from platform.features.security.identity.identity.presentation.bodies import (
    UpdateAdminUserPreferencesBody,
)

import pytest

pytestmark = pytest.mark.unit


class TestUpdateAdminUserPreferencesBody(TestCase):

    def test_accepts_iana_timezone_and_clock_format(self):
        body = UpdateAdminUserPreferencesBody({
            'timezone': 'America/Bogota',
            'date_format': 'DD/MM/YYYY',
            'time_format': '12',
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['timezone'], 'America/Bogota')
        self.assertEqual(body.validated_data['date_format'], 'DD/MM/YYYY')
        self.assertEqual(body.validated_data['time_format'], '12')

    def test_rejects_unknown_timezone(self):
        body = UpdateAdminUserPreferencesBody({'timezone': 'Not/AZone'})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'timezone')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_CHOICE)

    def test_rejects_unknown_date_format(self):
        body = UpdateAdminUserPreferencesBody({'date_format': 'YY-MM-DD'})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'date_format')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_CHOICE)

    def test_rejects_lowercase_date_mask(self):
        body = UpdateAdminUserPreferencesBody({'date_format': 'dd/mm/yyyy'})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'date_format')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_CHOICE)

    def test_rejects_unknown_time_format(self):
        body = UpdateAdminUserPreferencesBody({'time_format': '36'})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'time_format')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_CHOICE)

    def test_coerces_json_number_twelve_and_twenty_four(self):
        for raw, expected in ((12, '12'), (24, '24')):
            with self.subTest(raw=raw):
                body = UpdateAdminUserPreferencesBody({'time_format': raw})
                ok, errors = body.validate()
                self.assertTrue(ok, errors)
                self.assertEqual(body.validated_data['time_format'], expected)

    def test_rejects_json_number_outside_clock_choices(self):
        body = UpdateAdminUserPreferencesBody({'time_format': 36})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertEqual(errors[0].field, 'time_format')
        self.assertEqual(errors[0].code, ValidationCode.INVALID_TYPE)
