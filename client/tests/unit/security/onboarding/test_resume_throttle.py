"""Unit tests for the resume-link Redis throttle.

Properties under test:

  * SET-NX semantics: first call within the window wins, all others fail.
  * Window comes from the ``ONB_RESUME_WND_S`` runtime parameter (with a
    60-second default if the parameter row is missing).
  * Email is lower-cased so 'A@x.com' and 'a@x.com' share the same slot.
  * ``retry_after`` is omitted when the cache backend has no TTL.

Uses Django's LocMem cache as a stand-in for Redis — ``cache.add`` has
identical SET NX semantics on both backends.
"""
from unittest import mock

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.core.cache import caches
from django.test import SimpleTestCase, override_settings

import pytest

from client.features.security.lifecycle.onboarding.infrastructure.resume_throttle import (
    CacheResumeLinkThrottle,
)

pytestmark = pytest.mark.unit


PARAM_PATH = (
    'client.features.security.lifecycle.onboarding.infrastructure.resume_throttle.get_parameter'
)
CACHE_PATH = (
    'client.features.security.lifecycle.onboarding.infrastructure.resume_throttle._cache'
)


LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-onbtt'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-onbtt'},
}


@override_settings(CACHES=LOCMEM_CACHES)
class TestResumeThrottle(SimpleTestCase):

    def setUp(self):
        caches['auth'].clear()
        param_patch = mock.patch(PARAM_PATH, return_value=300)
        param_patch.start()
        self.addCleanup(param_patch.stop)
        self.throttle = CacheResumeLinkThrottle()

    def test_first_call_for_an_email_acquires_the_slot(self):
        self.assertTrue(self.throttle.try_acquire('user@example.com'))

    def test_second_call_within_window_is_blocked(self):
        self.assertTrue(self.throttle.try_acquire('user@example.com'))
        self.assertFalse(self.throttle.try_acquire('user@example.com'))
        self.assertIsNone(self.throttle.retry_after('user@example.com'))

    def test_retry_after_uses_cache_ttl_when_available(self):
        backend = mock.MagicMock()
        backend.add.return_value = False
        backend.ttl.return_value = 12.2
        with mock.patch(CACHE_PATH, return_value=backend):
            self.assertEqual(self.throttle.retry_after('user@example.com'), 13)

    def test_different_emails_have_independent_slots(self):
        self.assertTrue(self.throttle.try_acquire('a@example.com'))
        self.assertTrue(self.throttle.try_acquire('b@example.com'))

    def test_email_normalisation_is_case_insensitive(self):
        self.assertTrue(self.throttle.try_acquire('Foo@example.com'))
        self.assertFalse(self.throttle.try_acquire('foo@example.com'))
        self.assertFalse(self.throttle.try_acquire('FOO@EXAMPLE.COM'))

    def test_window_seconds_come_from_parameter(self):
        with mock.patch(PARAM_PATH, return_value=42) as param_mock:
            self.throttle.try_acquire('foo@example.com')
            param_mock.assert_called()
            self.assertEqual(param_mock.call_args.kwargs.get('default'), 60)
