"""Unit tests for OnboardingResendResumeLinkAPIView.

Behaviour exercised:

  * Public endpoint — no auth required.
  * Body validation: ``email`` must be present and a valid address.
  * Happy path → 204 with the success message envelope, no body data.
  * Use-case errors are surfaced through the global error handler:
      - ONBOARDING_NOT_FOUND (no active onboarding)        → 404
      - ONBOARDING_RESEND_THROTTLED (within window)        → 429
      - SERVER_ERROR (e.g. dispatcher blew up)             → 500
  * No cookie is ever set or cleared by this endpoint — it's an
    out-of-band trigger; the in-progress session is unchanged.

The view is patched at the module level so the real Redis-backed
store, dispatcher, and repository are never constructed.
"""
from unittest import mock
from unittest.mock import MagicMock

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

import pytest

from core.errors import AppErrorCode, OnboardingException

from client.features.security.lifecycle.onboarding.presentation.api import (
    OnboardingResendResumeLinkAPIView,
)
from client.features.security.lifecycle.onboarding.presentation.cookies import (
    ONBOARDING_COOKIE,
)

pytestmark = pytest.mark.unit


TestCase = SimpleTestCase

VIEW_PATH = 'client.features.security.lifecycle.onboarding.presentation.api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-resendlink'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-resendlink'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-resendlink'},
}


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/onboarding/resume-link/', data, format='json')
    return OnboardingResendResumeLinkAPIView.as_view()(request)


@override_settings(CACHES=LOCMEM_CACHES)
class _ResendLinkTestBase(TestCase):

    def setUp(self):
        # Stub parameter helpers so the view never hits the DB.
        reg_ttl = mock.patch(f'{VIEW_PATH}._registration_ttl_seconds', return_value=7 * 86400)
        reg_ttl.start()
        self.addCleanup(reg_ttl.stop)

        # Stub the repository / store factories.
        for fn in ('_repo', '_resume_token_store'):
            patch = mock.patch(f'{VIEW_PATH}.{fn}', return_value=MagicMock())
            patch.start()
            self.addCleanup(patch.stop)

        # Patch the use case so we observe execute() and inject errors.
        uc_patch = mock.patch(f'{VIEW_PATH}.ResendOnboardingResumeLinkUseCase')
        self.use_case_cls = uc_patch.start()
        self.addCleanup(uc_patch.stop)
        self.use_case_instance = self.use_case_cls.return_value
        self.use_case_instance.execute.return_value = None

        audit_patch = mock.patch(f'{VIEW_PATH}.audit_log')
        self.audit_mock = audit_patch.start()
        self.addCleanup(audit_patch.stop)


class TestValidation(_ResendLinkTestBase):

    def test_empty_body_is_400(self):
        response = _post({})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_invalid_email_is_400(self):
        response = _post({'email': 'not-an-email'})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_failed_validation_does_not_audit(self):
        _post({})
        self.audit_mock.assert_not_called()


class TestHappyPath(_ResendLinkTestBase):

    def test_returns_204_with_message(self):
        response = _post({'email': 'abandoned@example.com'})
        # ``wrap_response`` with status_code=204 still serialises the
        # envelope; the body is empty data + the message.
        self.assertEqual(response.status_code, 204)

    def test_use_case_called_with_email_from_body(self):
        _post({'email': 'abandoned@example.com'})
        self.use_case_instance.execute.assert_called_once_with(
            email='abandoned@example.com',
        )

    def test_does_not_set_or_clear_session_cookie(self):
        """Resend is out-of-band: the user might be hitting it from a
        different browser than the one holding the in-progress cookie.
        We must not touch ONBOARDING_COOKIE either way."""
        response = _post({'email': 'abandoned@example.com'})
        self.assertNotIn(ONBOARDING_COOKIE, response.cookies)

    def test_audit_log_records_resend_event(self):
        _post({'email': 'abandoned@example.com'})
        self.audit_mock.assert_called_once()
        args = self.audit_mock.call_args.args
        self.assertEqual(args[1], 'CompanyRegistration')
        # entity_id is None — the email alone is enough trail for resend.
        self.assertIsNone(args[2])
        self.assertEqual(args[3], 'RESUME_LINK_RESENT')
        self.assertIn('abandoned@example.com', args[4])


class TestErrorPaths(_ResendLinkTestBase):

    def test_throttled_returns_429(self):
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_RESEND_THROTTLED,
            retry_after=9,
        )

        response = _post({'email': 'abandoned@example.com'})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['error']['code'], 'ONB_012')
        self.assertEqual(response.data['error']['retry_after'], 9)
        self.assertEqual(response['Retry-After'], '9')

    def test_unknown_email_returns_404(self):
        """Privacy choice: same response for "no such email" as for
        "we have it but couldn't process". The body validator is the
        only step that exposes input shape; semantic absence collapses
        into the same 404 as a missing registration."""
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_NOT_FOUND,
        )

        response = _post({'email': 'unknown@example.com'})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'ONB_001')
