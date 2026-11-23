"""Unit tests for ConfirmEmailAPIView.

Behaviour checklist (see api.py):

  * Public endpoint — no auth, no permissions. The raw token is the only
    credential that matters.
  * Body validation: ``token`` is required, must be 20–128 chars. Outside
    that range → 400 from the body validator (use case never runs).
  * Happy path: the use case flips ``email_verified_at`` and returns the
    ``User``; the view emits both an audit log and a security log keyed
    on the user's pk/username, then returns 204 with no body.
  * Invalid/used/expired token: the use case raises
    ``AuthException(AUTH_TOKEN_INVALID)``; the global error handler turns
    that into a 401. Importantly, on this failure path NO audit/security
    log fires — those only happen after the user object is in hand.

Driven via ``APIRequestFactory`` so no DB or Redis is needed; the use
case and audit helpers are patched at the view module level.
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

from core.errors import AppErrorCode, AuthException

from client.features.security.lifecycle.auth.presentation.api import ConfirmEmailAPIView


TestCase = SimpleTestCase  # alias — avoids the DB setup that ``TestCase`` triggers

VIEW_PATH = 'client.features.security.lifecycle.auth.presentation.api'

# django_redis is a deployment-only dep — override with LocMem so the view's
# transitive ``caches[...]`` lookups (auth middleware, error handler) resolve.
# LOCATION strings are file-unique so AnonRateThrottle's per-IP bucket doesn't
# bleed across test files (LocMem dedups by LOCATION).
LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-confirm'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-confirm'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-confirm'},
}

# A plausible token — 32-byte url-safe values are 43 chars, well inside the
# 20–128 body bounds. Used as a generic happy-path stand-in.
VALID_TOKEN = 'a' * 43


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/auth/confirm-email/', data, format='json')
    return ConfirmEmailAPIView.as_view()(request)


def _confirmed_user(pk='user-pk', username='jsmith'):
    user = MagicMock()
    user.pk = pk
    user.username = username
    return user


@override_settings(CACHES=LOCMEM_CACHES)
class _ConfirmEmailViewTestBase(TestCase):

    def setUp(self):
        # Patch the use case class — the view instantiates it as
        # ``ConfirmEmailUseCase().execute(token)``.
        use_case_patch = mock.patch(f'{VIEW_PATH}.ConfirmEmailUseCase')
        self.use_case_cls = use_case_patch.start()
        self.addCleanup(use_case_patch.stop)
        self.use_case_instance = self.use_case_cls.return_value
        self.use_case_instance.execute.return_value = _confirmed_user()

        audit_patch = mock.patch(f'{VIEW_PATH}.audit_log')
        self.audit_mock = audit_patch.start()
        self.addCleanup(audit_patch.stop)

        security_patch = mock.patch(f'{VIEW_PATH}.security_log')
        self.security_mock = security_patch.start()
        self.addCleanup(security_patch.stop)


class TestValidation(_ConfirmEmailViewTestBase):

    def test_empty_body_is_400(self):
        """Without a token there is nothing to confirm — surface a
        validation error rather than running the use case with ``None``."""
        response = _post({})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_token_too_short_is_400(self):
        """The body validator pins the lower bound at 20 chars to weed out
        obviously malformed tokens before they hit the DB."""
        response = _post({'token': 'short'})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_token_too_long_is_400(self):
        """Upper bound is 128 chars — anything longer is rejected to keep
        request bodies bounded and avoid pathological hash inputs."""
        response = _post({'token': 'x' * 200})
        self.assertEqual(response.status_code, 400)
        self.use_case_instance.execute.assert_not_called()

    def test_failed_validation_does_not_log(self):
        """When the body fails validation we must not emit audit or
        security logs — there's no user yet to attribute the event to."""
        _post({})
        self.audit_mock.assert_not_called()
        self.security_mock.assert_not_called()


class TestHappyPath(_ConfirmEmailViewTestBase):

    def test_valid_token_returns_204(self):
        response = _post({'token': VALID_TOKEN})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_valid_token_calls_use_case_with_raw_token(self):
        """The view must forward the raw token verbatim — hashing happens
        inside the use case, not at the boundary."""
        _post({'token': VALID_TOKEN})
        self.use_case_instance.execute.assert_called_once_with(VALID_TOKEN)

    def test_response_has_no_body(self):
        """204 must be empty — the user object is internal and must not
        leak into the payload."""
        response = _post({'token': VALID_TOKEN})
        # DRF Response with no data serialises to b''.
        self.assertIn(getattr(response, 'data', None), (None, '', b''))

    def test_security_log_recorded_with_user_pk(self):
        """Security audit must be keyed on the user pk so analysts can
        correlate this confirmation with the original signup event."""
        user = _confirmed_user(pk='user-42', username='jsmith')
        self.use_case_instance.execute.return_value = user

        _post({'token': VALID_TOKEN})

        self.security_mock.assert_called_once()
        kwargs = self.security_mock.call_args.kwargs
        self.assertEqual(kwargs['event_type'], 'EMAIL_CONFIRMED')
        self.assertEqual(kwargs['target_user_id'], 'user-42')
        self.assertEqual(kwargs['resource'], '/api/v1/auth/confirm-email/')
        self.assertIn('username=jsmith', kwargs['detail'])

    def test_audit_log_recorded(self):
        """Audit log captures the User entity and the EMAIL_CONFIRMED
        action so the change is traceable from the entity timeline."""
        user = _confirmed_user(pk='user-42', username='jsmith')
        self.use_case_instance.execute.return_value = user

        _post({'token': VALID_TOKEN})

        self.audit_mock.assert_called_once()
        args = self.audit_mock.call_args.args
        # Signature: audit_log(request, entity_type, entity_id, action, description)
        self.assertEqual(args[1], 'User')
        self.assertEqual(args[2], 'user-42')
        self.assertEqual(args[3], 'EMAIL_CONFIRMED')


class TestErrorPaths(_ConfirmEmailViewTestBase):

    def test_invalid_token_returns_401(self):
        """Use case raises ``AuthException(AUTH_TOKEN_INVALID)`` for bad,
        used, or expired tokens; the global handler converts that to 401."""
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        response = _post({'token': VALID_TOKEN})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_token_does_not_log_success(self):
        """A failed confirmation must not appear as EMAIL_CONFIRMED in
        the audit trail — the success-path logs run only after the use
        case returns a user."""
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        _post({'token': VALID_TOKEN})

        self.audit_mock.assert_not_called()
        self.security_mock.assert_not_called()

    def test_error_response_carries_app_code(self):
        """The structured envelope must include ``error.code`` so the
        frontend can branch on AUTH_004 specifically (e.g. show a
        'request a new link' CTA)."""
        self.use_case_instance.execute.side_effect = AuthException(
            AppErrorCode.AUTH_TOKEN_INVALID,
        )

        response = _post({'token': VALID_TOKEN})

        self.assertEqual(response.data['error']['code'], 'AUTH_004')
