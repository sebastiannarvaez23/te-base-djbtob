"""Unit tests for PasswordResetValidateAPIView.

Behaviour checklist (see api.py):

  * Public endpoint — no auth, no permissions. The token is the only
    credential.
  * Body validation: ``token`` is required, 20–128 chars. Outside →
    400 from the body validator.
  * The use case is pure-read: even on success this endpoint MUST NOT
    burn the token (it is the SPA's pre-form check; the actual
    consumption happens at /confirm/).
  * Invalid/expired/used tokens raise AuthException(AUTH_TOKEN_INVALID)
    which the global handler turns into a 401.
"""
from unittest import mock

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

TestCase = SimpleTestCase

from core.errors import AppErrorCode, AuthException
from client.features.security.lifecycle.auth.presentation.api import PasswordResetValidateAPIView


VIEW_PATH = 'client.features.security.lifecycle.auth.presentation.api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-pwv'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-pwv'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-pwv'},
}

VALID_TOKEN = 'a' * 43


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/auth/password-reset/validate/', data, format='json')
    return PasswordResetValidateAPIView.as_view()(request)


@override_settings(CACHES=LOCMEM_CACHES)
class _ValidateViewTestBase(TestCase):

    def setUp(self):
        use_case_patch = mock.patch(f'{VIEW_PATH}.ValidatePasswordRecoveryTokenUseCase')
        self.use_case_cls = use_case_patch.start()
        self.addCleanup(use_case_patch.stop)
        self.use_case_instance = self.use_case_cls.return_value


class TestValidation(_ValidateViewTestBase):

    def test_empty_body_is_400(self):
        response = _post({})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_token_too_short_is_400(self):
        response = _post({'token': 'short'})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_token_too_long_is_400(self):
        response = _post({'token': 'x' * 200})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()


class TestHappyPath(_ValidateViewTestBase):

    def test_valid_token_returns_204(self):
        response = _post({'token': VALID_TOKEN})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_valid_token_calls_use_case_with_raw_token(self):
        """View must forward the raw token verbatim — hashing happens
        inside the use case."""
        _post({'token': VALID_TOKEN})
        self.use_case_instance.execute.assert_called_once_with(VALID_TOKEN)

    def test_response_has_no_body(self):
        """A leak of the user object on validate would let attackers
        probe tokens for valid accounts before submitting a real reset."""
        response = _post({'token': VALID_TOKEN})
        self.assertIn(getattr(response, 'data', None), (None, '', b''))


class TestErrorPaths(_ValidateViewTestBase):

    def test_invalid_token_returns_401(self):
        """AUTH_TOKEN_INVALID is mapped to 401 by the global handler so
        the SPA can route to the "request a new link" screen."""
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        response = _post({'token': VALID_TOKEN})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_error_response_carries_app_code(self):
        """The envelope must include AUTH_004 so the FE shows the
        right "link expired" copy."""
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        response = _post({'token': VALID_TOKEN})

        self.assertEqual(response.data['error']['code'], 'AUTH_004')
