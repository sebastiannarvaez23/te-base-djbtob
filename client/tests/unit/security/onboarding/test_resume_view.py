"""Unit tests for OnboardingResumeAPIView.

Behaviour checklist (see api.py):

  * Public endpoint — the magic-link token IS the credential.
  * Body validation: ``token`` is required, 20–128 chars. Outside that
    range → 400 from the body validator (use case never runs).
  * Happy path: the use case yields ``(session_token, registration_id)``;
    the view audits the RESUME event, returns 200 with
    ``registration_id``, and sets the ``onboarding_token`` HttpOnly
    cookie keyed to the new session token. The magic-link is one-shot
    (revoke happens inside the use case).
  * Unknown / expired / consumed token → use case raises
    ``OnboardingException(ONBOARDING_INVALID_TOKEN)``; global handler
    renders 401. No cookie is set on this path.

Driven via ``APIRequestFactory`` so no DB or Redis is needed; the use
case, parameter helpers, and audit are patched at the view module level.
"""
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

from client.features.security.lifecycle.onboarding.presentation.api import (
    OnboardingResumeAPIView,
)
from client.features.security.lifecycle.onboarding.presentation.cookies import (
    ONBOARDING_COOKIE,
)


TestCase = SimpleTestCase  # alias — avoids the DB setup that ``TestCase`` triggers

VIEW_PATH = 'client.features.security.lifecycle.onboarding.presentation.api'

# LOCATION strings are file-unique so AnonRateThrottle's per-IP bucket doesn't
# bleed across test files (LocMem dedups by LOCATION).
LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-onbresume'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-onbresume'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-onbresume'},
}

REG_ID = UUID('22222222-2222-2222-2222-222222222222')
VALID_TOKEN = 'a' * 43  # url-safe(32) length, comfortably inside 20–128 bounds


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/onboarding/resume/', data, format='json')
    return OnboardingResumeAPIView.as_view()(request)


@override_settings(CACHES=LOCMEM_CACHES)
class _ResumeViewTestBase(TestCase):

    def setUp(self):
        token_ttl_patch = mock.patch(f'{VIEW_PATH}._token_ttl_seconds', return_value=7200)
        token_ttl_patch.start()
        self.addCleanup(token_ttl_patch.stop)

        for fn in ('_repo', '_token_store', '_resume_token_store'):
            patch = mock.patch(f'{VIEW_PATH}.{fn}', return_value=MagicMock())
            patch.start()
            self.addCleanup(patch.stop)

        use_case_patch = mock.patch(f'{VIEW_PATH}.ResumeOnboardingUseCase')
        self.use_case_cls = use_case_patch.start()
        self.addCleanup(use_case_patch.stop)
        self.use_case_instance = self.use_case_cls.return_value
        self.use_case_instance.execute.return_value = ('session-token', REG_ID)

        audit_patch = mock.patch(f'{VIEW_PATH}.audit_log')
        self.audit_mock = audit_patch.start()
        self.addCleanup(audit_patch.stop)


class TestValidation(_ResumeViewTestBase):

    def test_empty_body_is_400(self):
        response = _post({})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_token_too_short_is_400(self):
        response = _post({'token': 'short'})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()


class TestHappyPath(_ResumeViewTestBase):

    def test_returns_200_with_registration_id(self):
        response = _post({'token': VALID_TOKEN})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['registration_id'], str(REG_ID))

    def test_use_case_called_with_raw_token(self):
        """Token is forwarded verbatim — the resume store hashes/looks up
        on its own; the view must not transform the value."""
        _post({'token': VALID_TOKEN})

        self.use_case_instance.execute.assert_called_once_with(VALID_TOKEN)

    def test_cookie_is_set_with_issued_session_token(self):
        """The freshly minted session token (not the magic-link) ends up
        in the cookie. The magic-link is single-use and already revoked
        inside the use case."""
        response = _post({'token': VALID_TOKEN})

        self.assertIn(ONBOARDING_COOKIE, response.cookies)
        morsel = response.cookies[ONBOARDING_COOKIE]
        self.assertEqual(morsel.value, 'session-token')
        self.assertTrue(morsel['httponly'])

    def test_audit_log_records_resume(self):
        _post({'token': VALID_TOKEN})

        self.audit_mock.assert_called_once()
        args = self.audit_mock.call_args.args
        self.assertEqual(args[1], 'CompanyRegistration')
        self.assertEqual(args[2], REG_ID)
        self.assertEqual(args[3], 'RESUME')


class TestErrorPaths(_ResumeViewTestBase):

    def test_unknown_token_returns_401(self):
        """The use case raises ONBOARDING_INVALID_TOKEN for unknown,
        consumed, or expired magic-links; global handler renders 401."""
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_INVALID_TOKEN,
        )

        response = _post({'token': VALID_TOKEN})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['error']['code'], 'ONB_007')

    def test_unknown_token_does_not_set_cookie(self):
        """A failed resume must not seed a cookie — otherwise replaying
        the magic-link would still hand the attacker a session handle."""
        self.use_case_instance.execute.side_effect = OnboardingException(
            AppErrorCode.ONBOARDING_INVALID_TOKEN,
        )

        response = _post({'token': VALID_TOKEN})

        self.assertNotIn(ONBOARDING_COOKIE, response.cookies)
