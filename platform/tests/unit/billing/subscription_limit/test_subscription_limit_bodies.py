"""Unit tests for subscription-limit request bodies (window validation type)."""
import uuid
import unittest

from core.validators import ValidationCode
from platform.features.billing.subscription.subscription_limit.presentation.bodies import (
    CreateSubscriptionLimitBody,
    UpdateSubscriptionLimitBody,
)


def _create_payload(**overrides):
    data = {
        'subscription': str(uuid.uuid4()),
        'functionality': str(uuid.uuid4()),
        'max_value': 3,
        'validation_type': 'window',
        'window_hours': 3,
    }
    data.update(overrides)
    return data


class TestCreateSubscriptionLimitBody(unittest.TestCase):

    def test_accepts_window_with_hours(self):
        body = CreateSubscriptionLimitBody(_create_payload())
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['validation_type'], 'window')
        self.assertEqual(body.validated_data['window_hours'], 3)

    def test_window_requires_hours(self):
        payload = _create_payload()
        del payload['window_hours']
        body = CreateSubscriptionLimitBody(payload)
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(
            e.field == 'window_hours' and e.code == ValidationCode.REQUIRED
            for e in errors
        ))

    def test_daily_strips_window_hours(self):
        body = CreateSubscriptionLimitBody(_create_payload(
            validation_type='daily', window_hours=3,
        ))
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertIsNone(body.validated_data['window_hours'])

    def test_lifetime_strips_window_hours(self):
        body = CreateSubscriptionLimitBody(_create_payload(
            validation_type='lifetime', window_hours=3,
        ))
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertIsNone(body.validated_data['window_hours'])

    def test_hours_below_minimum_rejected(self):
        body = CreateSubscriptionLimitBody(_create_payload(window_hours=0))
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(e.field == 'window_hours' and e.code == ValidationCode.MIN_VALUE for e in errors))

    def test_hours_above_maximum_rejected(self):
        body = CreateSubscriptionLimitBody(_create_payload(window_hours=169))
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(e.field == 'window_hours' and e.code == ValidationCode.MAX_VALUE for e in errors))

    def test_unknown_validation_type_rejected(self):
        body = CreateSubscriptionLimitBody(_create_payload(validation_type='monthly'))
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(
            e.field == 'validation_type' and e.code == ValidationCode.INVALID_CHOICE
            for e in errors
        ))

    def test_name_is_optional(self):
        body = CreateSubscriptionLimitBody(_create_payload())
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data.get('name', ''), '')

    def test_name_too_long_rejected(self):
        body = CreateSubscriptionLimitBody(_create_payload(name='x' * 151))
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(
            e.field == 'name' and e.code == ValidationCode.MAX_LENGTH for e in errors
        ))

    def test_max_value_below_zero_rejected(self):
        body = CreateSubscriptionLimitBody(_create_payload(max_value=-1, validation_type='lifetime'))
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(e.field == 'max_value' for e in errors))


class TestUpdateSubscriptionLimitBody(unittest.TestCase):

    def test_switching_to_window_without_hours_allowed_at_body(self):
        """Hours pueden reutilizarse del registro; el use case valida el invariante."""
        body = UpdateSubscriptionLimitBody({'validation_type': 'window'})
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertNotIn('window_hours', body.validated_data)

    def test_switching_to_window_with_explicit_null_hours_rejected(self):
        body = UpdateSubscriptionLimitBody({
            'validation_type': 'window',
            'window_hours': None,
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(
            e.field == 'window_hours' and e.code == ValidationCode.REQUIRED
            for e in errors
        ))

    def test_switching_to_window_with_hours(self):
        body = UpdateSubscriptionLimitBody({
            'validation_type': 'window',
            'window_hours': 3,
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['window_hours'], 3)

    def test_switching_to_daily_strips_hours(self):
        body = UpdateSubscriptionLimitBody({
            'validation_type': 'daily',
            'window_hours': 6,
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertIsNone(body.validated_data['window_hours'])

    def test_partial_update_without_type_keeps_hours(self):
        body = UpdateSubscriptionLimitBody({'max_value': 10, 'window_hours': 4})
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['window_hours'], 4)
        self.assertNotIn('validation_type', body.validated_data)

    def test_name_is_optional(self):
        body = UpdateSubscriptionLimitBody({'max_value': 5})
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertNotIn('name', body.validated_data)

    def test_name_too_long_rejected(self):
        body = UpdateSubscriptionLimitBody({'name': 'x' * 151})
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(
            e.field == 'name' and e.code == ValidationCode.MAX_LENGTH for e in errors
        ))
