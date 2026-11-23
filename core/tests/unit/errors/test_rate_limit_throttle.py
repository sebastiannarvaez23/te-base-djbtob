"""DRF throttle → global handler: Too many requests (RL_001).

The transversal layer is the combination of:

  * ``DEFAULT_THROTTLE_CLASSES`` / per-view ``throttle_classes``
  * ``app_exception_handler`` mapping ``Throttled`` to ``RL_001``
  * ``error.retry_after`` + header ``Retry-After``

These tests drive a real APIView (no DB) so the cut happens where DRF
would cut production traffic: before the view body runs.
"""
from __future__ import annotations

import re

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.core.cache import caches
from django.test import SimpleTestCase, override_settings
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

import pytest

from core.decorators.response import wrap_response
from core.errors.exceptions import RateLimitException
from core.errors.retry_after import RETRY_AFTER_HEADER


pytestmark = pytest.mark.unit

_SPANISH = r'[áéíóúñüÁÉÍÓÚÑÜ¿¡]'

LOCMEM_CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'rl-layer-throttle',
    },
    'access': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'rl-layer-access',
    },
    'auth': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'rl-layer-auth',
        'KEY_PREFIX': 'auth',
    },
}


class _OncePerMinute(AnonRateThrottle):
    """One anonymous request per IP per minute — deterministic for tests."""

    scope = 'rl_once'
    rate = '1/min'


class _ProbeView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [_OncePerMinute]
    hit = 0

    def get(self, request):
        type(self).hit += 1
        return wrap_response({'ok': True})


class _RaiseRateLimitView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        raise RateLimitException(retry_after=8)


def _get(view, *, ip='10.20.30.40', path='/api/v1/probe/'):
    factory = APIRequestFactory()
    request = factory.get(path)
    request.META['REMOTE_ADDR'] = ip
    request.request_id = 'req-throttle'
    return view.as_view()(request)


@override_settings(CACHES=LOCMEM_CACHES)
class TestAnonThrottleCutsWithRl001(SimpleTestCase):

    def setUp(self):
        caches['default'].clear()
        _ProbeView.hit = 0

    def test_first_request_is_allowed(self):
        response = _get(_ProbeView)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['type'], 'success')
        self.assertEqual(response.data['data'], {'ok': True})
        self.assertEqual(_ProbeView.hit, 1)

    def test_second_request_is_rl_001_and_does_not_run_the_view(self):
        first = _get(_ProbeView)
        second = _get(_ProbeView)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.data['type'], 'error')
        self.assertEqual(second.data['status_code'], 429)
        self.assertEqual(second.data['message'], 'Too many requests')
        self.assertEqual(second.data['detail'], 'Too many requests.')
        self.assertEqual(second.data['error']['code'], 'RL_001')
        self.assertEqual(second.data['error']['trace_id'], 'req-throttle')
        self.assertIsInstance(second.data['error']['retry_after'], int)
        self.assertGreaterEqual(second.data['error']['retry_after'], 1)
        self.assertEqual(
            second[RETRY_AFTER_HEADER],
            str(second.data['error']['retry_after']),
        )
        self.assertNotIn('incident', second.data['error'])
        self.assertEqual(_ProbeView.hit, 1)

    def test_second_request_copy_is_english(self):
        _get(_ProbeView)
        response = _get(_ProbeView)
        body = f"{response.data['message']} {response.data['detail']}"

        self.assertIsNone(re.search(_SPANISH, body))

    def test_distinct_ips_have_independent_buckets(self):
        first = _get(_ProbeView, ip='10.0.0.1')
        other = _get(_ProbeView, ip='10.0.0.2')
        blocked = _get(_ProbeView, ip='10.0.0.1')

        self.assertEqual(first.status_code, 200)
        self.assertEqual(other.status_code, 200)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(_ProbeView.hit, 2)


@override_settings(CACHES=LOCMEM_CACHES)
class TestRateLimitExceptionFromView(SimpleTestCase):

    def test_raised_rate_limit_uses_the_same_envelope(self):
        response = _get(_RaiseRateLimitView)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['message'], 'Too many requests')
        self.assertEqual(response.data['detail'], 'Too many requests.')
        self.assertEqual(response.data['error']['code'], 'RL_001')
        self.assertEqual(response.data['error']['retry_after'], 8)
        self.assertEqual(response[RETRY_AFTER_HEADER], '8')
        self.assertNotIn('retry_after', response.data['error'].get('context') or {})
