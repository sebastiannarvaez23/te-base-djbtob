"""Unit tests for PasswordResetConfirmAPIView.

Behaviour checklist (see api.py):

  * Public endpoint — token + new password are the only credentials.
  * Body validation: ``token`` (20–128) and ``password`` (8–64) required.
  * Happy path: use case rotates the password and marks the token used;
    the view then revokes every active client refresh token for that
    user (anti-takeover) and emits both audit and security logs.
  * Failure path (invalid/used/expired token): AuthException(AUTH_004)
    bubbles up; the view emits a PWD_RESET_FAILED security event but no
    audit log (we don't have a user to attribute it to). Refresh tokens
    are NOT revoked.
  * Refresh revocation failures are swallowed so the password rotation
    success isn't masked by a transient Redis outage.
"""
from unittest import mock
from unittest.mock import MagicMock

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
from client.features.security.lifecycle.auth.presentation.api import PasswordResetConfirmAPIView


VIEW_PATH = 'client.features.security.lifecycle.auth.presentation.api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-pwc'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-pwc'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-pwc'},
}

VALID_TOKEN = 'a' * 43
VALID_PASSWORD = 'S3cret-Pa$s'


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/auth/password-reset/confirm/', data, format='json')
    return PasswordResetConfirmAPIView.as_view()(request)


def _user(pk='user-pk', username='jsmith'):
    user = MagicMock()
    user.pk = pk
    user.username = username
    return user


@override_settings(CACHES=LOCMEM_CACHES)
class _ConfirmViewTestBase(TestCase):

    def setUp(self):
        use_case_patch = mock.patch(f'{VIEW_PATH}.ConsumePasswordRecoveryTokenUseCase')
        self.use_case_cls = use_case_patch.start()
        self.addCleanup(use_case_patch.stop)
        self.use_case_instance = self.use_case_cls.return_value
        self.use_case_instance.execute.return_value = _user()

        refresh_patch = mock.patch(f'{VIEW_PATH}.RedisClientRefreshStore')
        self.refresh_mock = refresh_patch.start().return_value
        self.addCleanup(refresh_patch.stop)

        audit_patch = mock.patch(f'{VIEW_PATH}.audit_log')
        self.audit_mock = audit_patch.start()
        self.addCleanup(audit_patch.stop)

        security_patch = mock.patch(f'{VIEW_PATH}.security_log')
        self.security_mock = security_patch.start()
        self.addCleanup(security_patch.stop)


class TestValidation(_ConfirmViewTestBase):

    def test_empty_body_is_400(self):
        response = _post({})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_missing_token_is_400(self):
        response = _post({'password': VALID_PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_missing_password_is_400(self):
        response = _post({'token': VALID_TOKEN})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_short_password_is_400(self):
        """8-char minimum is enforced at the boundary so the use case
        cannot accept a weak password by accident."""
        response = _post({'token': VALID_TOKEN, 'password': 'short'})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_validation_failure_does_not_call_refresh_revoke(self):
        """A 400 must not touch session state — only confirmed rotations
        revoke refresh tokens, otherwise this is a DoS surface."""
        _post({})
        self.refresh_mock.revoke_all_for_user.assert_not_called()


class TestHappyPath(_ConfirmViewTestBase):

    def test_valid_payload_returns_204(self):
        response = _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_use_case_called_with_raw_token_and_password(self):
        """The view must forward both fields verbatim — the use case
        owns hashing and password storage."""
        _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})
        self.use_case_instance.execute.assert_called_once_with(
            raw_token=VALID_TOKEN, new_password=VALID_PASSWORD,
        )

    def test_revokes_all_client_refresh_tokens(self):
        """Anti-takeover: an attacker holding a stale refresh cookie must
        lose access the instant the password rotates."""
        user = _user(pk='user-42')
        self.use_case_instance.execute.return_value = user

        _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.refresh_mock.revoke_all_for_user.assert_called_once_with('user-42')

    def test_refresh_revoke_failure_is_swallowed(self):
        """A Redis hiccup during revocation must not bubble up — the
        password was already rotated; failing the response would leave
        the user thinking the reset didn't take."""
        self.refresh_mock.revoke_all_for_user.side_effect = RuntimeError('redis down')

        response = _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.assertEqual(response.status_code, 204)

    def test_security_log_recorded_with_user_pk(self):
        user = _user(pk='user-42', username='jsmith')
        self.use_case_instance.execute.return_value = user

        _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.security_mock.assert_called_once()
        kwargs = self.security_mock.call_args.kwargs
        self.assertEqual(kwargs['event_type'], 'PWD_RESET_COMPLETED')
        self.assertEqual(kwargs['target_user_id'], 'user-42')
        self.assertIn('username=jsmith', kwargs['detail'])

    def test_audit_log_recorded(self):
        user = _user(pk='user-42', username='jsmith')
        self.use_case_instance.execute.return_value = user

        _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.audit_mock.assert_called_once()
        args = self.audit_mock.call_args.args
        self.assertEqual(args[1], 'User')
        self.assertEqual(args[2], 'user-42')
        self.assertEqual(args[3], 'PASSWORD_RESET')


class TestErrorPaths(_ConfirmViewTestBase):

    def test_invalid_token_returns_401(self):
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        response = _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_does_not_revoke_refresh(self):
        """Critical: a failed reset must NOT log the user out. Otherwise
        an attacker probing tokens could trivially lock the legit user
        out of every active session."""
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.refresh_mock.revoke_all_for_user.assert_not_called()

    def test_invalid_token_emits_failure_security_log(self):
        """We DO record the attempt — analysts need to see brute-force
        patterns even when the token didn't match."""
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.security_mock.assert_called_once()
        kwargs = self.security_mock.call_args.kwargs
        self.assertEqual(kwargs['event_type'], 'PWD_RESET_FAILED')

    def test_invalid_token_does_not_emit_audit_log(self):
        """Audit log is keyed on entity_id — without a user we have
        nothing to attribute the entry to. Security log carries the
        attempt instead."""
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.audit_mock.assert_not_called()

    def test_error_response_carries_app_code(self):
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        response = _post({'token': VALID_TOKEN, 'password': VALID_PASSWORD})

        self.assertEqual(response.data['error']['code'], 'AUTH_004')
