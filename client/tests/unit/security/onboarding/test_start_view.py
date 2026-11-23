"""Unit tests for OnboardingStartAPIView.

Behaviour checklist (see api.py):

  * Public endpoint — onboarding is unauthenticated by definition.
  * Body validation: ``email`` is required, must be a valid email, max
    254 chars (RFC 5321). Bad input → 400 from the body validator;
    use case never runs.
  * Happy path: the use case yields ``(token, reg)``; the view audits
    the CREATE event, returns 201 with ``registration_id`` + ``expires_at``,
    and sets the ``onboarding_token`` HttpOnly cookie keyed to the issued
    token.
  * Duplicate active onboarding: use case raises
    ``OnboardingException(ONBOARDING_DUPLICATE_EMAIL)``; the global
    handler converts that to 409. No cookie is set on this path.

Driven via ``APIRequestFactory`` so no DB or Redis is needed; the use
case, parameter helpers, and audit are patched at the view module level.
"""
from datetime import datetime, timezone
from unittest import mock
from unittest.mock import MagicMock
from uuid import UUID

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from core.errors import AppErrorCode, OnboardingException
from core.instants import serialize_instant

from client.features.security.lifecycle.onboarding.presentation.api import (
    OnboardingStartAPIView,
)
from client.features.security.lifecycle.onboarding.presentation.cookies import (
    ONBOARDING_COOKIE,
)


TestCase = SimpleTestCase  # alias — avoids the DB setup that ``TestCase`` triggers

VIEW_PATH = 'client.features.security.lifecycle.onboarding.presentation.api'

# django_redis is a deployment-only dep — override with LocMem so transitive
# ``caches[...]`` lookups (auth middleware, error handler) resolve.
# LOCATION strings are file-unique so AnonRateThrottle's per-IP bucket doesn't
# bleed across test files (LocMem dedups by LOCATION).
LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-onbstart'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-onbstart'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-onbstart'},
}

REG_ID = UUID('11111111-1111-1111-1111-111111111111')
EXPIRES_AT = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/onboarding/start/', data, format='json')
    return OnboardingStartAPIView.as_view()(request)


def _registration(reg_id=REG_ID, email='founder@example.com', expires_at=EXPIRES_AT):
    reg = MagicMock()
    reg.id = reg_id
    reg.email = email
    reg.expires_at = expires_at
    return reg


@override_settings(CACHES=LOCMEM_CACHES)
class _StartViewTestBase(TestCase):

    def setUp(self):
        # Patch parameter lookups so the view doesn't hit the DB for the
        # Parameter table.
        token_ttl_patch = mock.patch(f'{VIEW_PATH}._token_ttl_seconds', return_value=7200)
        token_ttl_patch.start()
        self.addCleanup(token_ttl_patch.stop)

        reg_ttl_patch = mock.patch(
            f'{VIEW_PATH}._registration_ttl_seconds', return_value=7 * 86400,
        )
        reg_ttl_patch.start()
        self.addCleanup(reg_ttl_patch.stop)

        # Stub the repository / token-store factories so we don't construct
        # the real Redis-backed objects.
        for fn in ('_repo', '_token_store', '_resume_token_store'):
            patch = mock.patch(f'{VIEW_PATH}.{fn}', return_value=MagicMock())
            patch.start()
            self.addCleanup(patch.stop)

        use_case_patch = mock.patch(f'{VIEW_PATH}.StartOnboardingUseCase')
        self.use_case_cls = use_case_patch.start()
        self.addCleanup(use_case_patch.stop)
        self.use_case_instance = self.use_case_cls.return_value
        self.use_case_instance.execute.return_value = ('session-token', _registration())

        audit_patch = mock.patch(f'{VIEW_PATH}.audit_log')
        self.audit_mock = audit_patch.start()
        self.addCleanup(audit_patch.stop)


class TestValidation(_StartViewTestBase):

    def test_empty_body_is_400(self):
        response = _post({})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_invalid_email_format_is_400(self):
        response = _post({'email': 'not-an-email'})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_email_too_long_is_400(self):
        """Bound at 254 chars (RFC 5321 max). Anything longer is rejected
        before we even attempt a DB lookup."""
        long_local = 'a' * 250
        response = _post({'email': f'{long_local}@x.co'})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_failed_validation_does_not_audit(self):
        _post({})
        self.audit_mock.assert_not_called()


class TestHappyPath(_StartViewTestBase):

    def test_returns_201_with_registration_payload(self):
        response = _post({'email': 'founder@example.com'})

        self.assertEqual(response.status_code, 201)
        data = response.data['data']
        self.assertEqual(data['registration_id'], str(REG_ID))
        self.assertEqual(data['expires_at'], serialize_instant(EXPIRES_AT))

    def test_use_case_called_with_email_from_body(self):
        _post({'email': 'founder@example.com'})

        self.use_case_instance.execute.assert_called_once_with(
            email='founder@example.com',
        )

    def test_cookie_is_set_with_issued_token(self):
        """The session token returned by the use case must end up in the
        HttpOnly ``onboarding_token`` cookie — the cookie is the handle
        the client sends back on subsequent step calls."""
        response = _post({'email': 'founder@example.com'})

        self.assertIn(ONBOARDING_COOKIE, response.cookies)
        morsel = response.cookies[ONBOARDING_COOKIE]
        self.assertEqual(morsel.value, 'session-token')
        self.assertTrue(morsel['httponly'])

    def test_cookie_max_age_matches_token_ttl(self):
        """Cookie lifetime must mirror the token TTL — a longer cookie
        would still resolve to a dead session in Redis (just churns 401s)."""
        response = _post({'email': 'founder@example.com'})

        morsel = response.cookies[ONBOARDING_COOKIE]
        self.assertEqual(int(morsel['max-age']), 7200)

    def test_audit_log_records_create_with_registration_id(self):
        _post({'email': 'founder@example.com'})

        self.audit_mock.assert_called_once()
        args = self.audit_mock.call_args.args
        # Signature: audit_log(request, entity_type, entity_id, action, description)
        self.assertEqual(args[1], 'CompanyRegistration')
        self.assertEqual(args[2], REG_ID)
        self.assertEqual(args[3], 'CREATE')
        self.assertIn('founder@example.com', args[4])


class TestErrorPaths(_StartViewTestBase):

    def test_duplicate_active_email_returns_409(self):
        """The use case raises ONBOARDING_DUPLICATE_EMAIL when an active
        registration already exists; the global handler renders 409."""
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_DUPLICATE_EMAIL,
        )

        response = _post({'email': 'founder@example.com'})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'ONB_005')

    def test_duplicate_email_does_not_set_cookie(self):
        """No cookie may leak from an aborted start — otherwise a duplicate
        attempt would clobber the original registration's session handle."""
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_DUPLICATE_EMAIL,
        )

        response = _post({'email': 'founder@example.com'})

        self.assertNotIn(ONBOARDING_COOKIE, response.cookies)

    def test_duplicate_email_does_not_audit(self):
        """Audit log is reserved for successful CREATE events — a 409
        rejection is already captured by the security log on AUTH_FAILURE
        path inside the global handler."""
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_DUPLICATE_EMAIL,
        )

        _post({'email': 'founder@example.com'})

        self.audit_mock.assert_not_called()

    def test_email_already_owns_an_account_returns_409_onb_011(self):
        """When the email belongs to a finalized User, the use case raises
        ONBOARDING_EMAIL_ALREADY_REGISTERED. The view must surface that as
        409 ONB_011 (different action than ONB_005: the user should sign in,
        not resume an in-progress registration)."""
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_EMAIL_ALREADY_REGISTERED,
        )

        response = _post({'email': 'founder@example.com'})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'ONB_011')
        self.assertNotIn(ONBOARDING_COOKIE, response.cookies)
