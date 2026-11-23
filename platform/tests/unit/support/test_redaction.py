"""Unit tests for shared incident evidence redaction."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

from platform.features.support.incidents.incident.application.redaction import (
    is_sensitive_key,
    redact_secret_pairs,
    redact_text_value,
)


class RedactionTests(TestCase):

    def test_is_sensitive_key(self):
        self.assertTrue(is_sensitive_key('access_token'))
        self.assertFalse(is_sensitive_key('user_id'))

    def test_redact_secret_pairs(self):
        self.assertEqual(
            redact_secret_pairs('login password=super-secret'),
            'login password=***',
        )

    def test_redact_text_value_clips(self):
        text = redact_text_value('token=abc ' + ('x' * 600), max_len=20)
        self.assertLessEqual(len(text), 20)
