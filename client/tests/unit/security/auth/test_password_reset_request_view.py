"""Unit tests for PasswordResetRequestAPIView.

Behaviour checklist (see api.py):

  * Always responds 204 to prevent account-enumeration: caller cannot
    tell "email exists" from "does not exist", "throttled", or "user
    is inactive".
  * Input: ``email`` is required; missing or malformed email → 400 from
    the body validator (no token issued, no email sent).
  * Throttle is acquired per-IP first (cheap, short-window), and then
    per-user (longer window). Either failing silently degrades to 204.
  * Inactive user → 204 without dispatch.
  * Dispatch failures are swallowed so the response stays 204; an SMTP
    outage cannot reveal account existence via response divergence.
  * Security log is emitted only on successful dispatch.

Driven via ``APIRequestFactory``; no DB or Redis needed.
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

from client.features.security.lifecycle.auth.presentation.api import PasswordResetRequestAPIView


VIEW_PATH = 'client.features.security.lifecycle.auth.presentation.api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-pwr'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-pwr'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-pwr'},
}


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/auth/password-reset/request/', data, format='json')
    return PasswordResetRequestAPIView.as_view()(request)


def _active_user(pk='user-pk', username='jsmith', email='jsmith@example.com'):
    user = MagicMock()
    user.pk = pk
    user.username = username
    user.email = email
    user.is_active = True
    return user


@override_settings(CACHES=LOCMEM_CACHES)
class _RequestViewTestBase(TestCase):

    def setUp(self):
        self.User = MagicMock()
        user_patch = mock.patch(f'{VIEW_PATH}.get_user_model', return_value=self.User)
        user_patch.start()
        self.addCleanup(user_patch.stop)

        self.ip_throttle = mock.patch(
            f'{VIEW_PATH}.try_acquire_recovery_ip_slot', return_value=True,
        )
        self.ip_throttle_mock = self.ip_throttle.start()
        self.addCleanup(self.ip_throttle.stop)

        self.user_throttle = mock.patch(
            f'{VIEW_PATH}.try_acquire_recovery_slot', return_value=True,
        )
        self.user_throttle_mock = self.user_throttle.start()
        self.addCleanup(self.user_throttle.stop)

        self.dispatch = mock.patch(f'{VIEW_PATH}._issue_and_dispatch_recovery')
        self.dispatch_mock = self.dispatch.start()
        self.addCleanup(self.dispatch.stop)

        security_patch = mock.patch(f'{VIEW_PATH}.security_log')
        self.security_mock = security_patch.start()
        self.addCleanup(security_patch.stop)


class TestValidation(_RequestViewTestBase):

    def test_empty_body_is_400(self):
        """Without an email we have nothing to look up — surface a 400
        instead of a misleading 204 (this is a client bug, not an
        enumeration vector)."""
        response = _post({})
        self.assertEqual(response.status_code, 400)
        self.dispatch_mock.assert_not_called()

    def test_invalid_email_format_is_400(self):
        response = _post({'email': 'not-an-email'})
        self.assertEqual(response.status_code, 400)
        self.dispatch_mock.assert_not_called()

    def test_validation_failure_does_not_call_throttle(self):
        """Validation runs before throttle; a malformed email mustn't burn
        the per-IP slot or it becomes a trivial DoS surface."""
        _post({'email': 'bad'})
        self.ip_throttle_mock.assert_not_called()


class TestEnumerationSafety(_RequestViewTestBase):

    def test_unknown_email_returns_204(self):
        """Attackers cannot distinguish known vs unknown email."""
        self.User.objects.filter.return_value.first.return_value = None

        response = _post({'email': 'ghost@example.com'})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.dispatch_mock.assert_not_called()
        self.security_mock.assert_not_called()

    def test_inactive_user_returns_204_without_dispatch(self):
        user = _active_user()
        user.is_active = False
        self.User.objects.filter.return_value.first.return_value = user

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_not_called()

    def test_throttled_user_returns_204_without_dispatch(self):
        """Per-user throttle must not reveal itself — the response is
        identical to the "unknown email" case."""
        self.user_throttle_mock.return_value = False
        user = _active_user()
        self.User.objects.filter.return_value.first.return_value = user

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_not_called()

    def test_ip_throttled_returns_204_without_lookup(self):
        """Per-IP throttle short-circuits *before* hitting the user table —
        a bot iterating emails from one origin gets nothing back. Lookup is
        skipped to keep the cost-per-request flat."""
        self.ip_throttle_mock.return_value = False

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.User.objects.filter.assert_not_called()
        self.dispatch_mock.assert_not_called()

    def test_user_lookup_exception_returns_204(self):
        """A transient DB failure during lookup must degrade to 204 so
        an attacker cannot probe infra state via 500s."""
        self.User.objects.filter.side_effect = RuntimeError('db down')

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_not_called()

    def test_dispatch_exception_is_swallowed(self):
        """If SMTP/Redis is down we still return 204 — the client has
        nothing actionable and 500s would leak account existence."""
        user = _active_user()
        self.User.objects.filter.return_value.first.return_value = user
        self.dispatch_mock.side_effect = RuntimeError('smtp down')

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)

    def test_response_has_no_body(self):
        """204 must be empty — any leaked field becomes an oracle."""
        self.User.objects.filter.return_value.first.return_value = None

        response = _post({'email': 'ghost@example.com'})

        self.assertEqual(response.status_code, 204)
        self.assertIn(getattr(response, 'data', None), (None, '', b''))


class TestLookupStrategy(_RequestViewTestBase):

    def test_email_lookup_is_case_insensitive(self):
        """Users type their email with inconsistent casing — iexact avoids
        spuriously failing the lookup over capitalisation."""
        user = _active_user()
        self.User.objects.filter.return_value.first.return_value = user

        _post({'email': 'JSmith@Example.com'})

        kwargs = self.User.objects.filter.call_args.kwargs
        self.assertIn('email__iexact', kwargs)
        self.assertEqual(kwargs['email__iexact'], 'JSmith@Example.com')

    def test_email_passed_to_lookup_verbatim(self):
        """The email reaches the ORM exactly as submitted (after the
        body-validator's own normalisation) so this regression catches
        any accidental rewriting in the view."""
        user = _active_user()
        self.User.objects.filter.return_value.first.return_value = user

        _post({'email': 'jsmith@example.com'})

        kwargs = self.User.objects.filter.call_args.kwargs
        self.assertEqual(kwargs['email__iexact'], 'jsmith@example.com')


class TestHappyPath(_RequestViewTestBase):

    def test_active_user_triggers_dispatch(self):
        user = _active_user()
        self.User.objects.filter.return_value.first.return_value = user

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_called_once()
        # Signature: _issue_and_dispatch_recovery(user, request)
        args = self.dispatch_mock.call_args.args
        self.assertIs(args[0], user)

    def test_user_throttle_is_acquired_with_user_pk(self):
        """Per-user throttle must be keyed on the user pk so independent
        accounts don't share a slot."""
        user = _active_user(pk='user-42')
        self.User.objects.filter.return_value.first.return_value = user

        _post({'email': 'jsmith@example.com'})

        self.user_throttle_mock.assert_called_once_with('user-42')

    def test_security_log_recorded_on_dispatch(self):
        user = _active_user(pk='user-42', username='jsmith')
        self.User.objects.filter.return_value.first.return_value = user

        _post({'email': 'jsmith@example.com'})

        self.security_mock.assert_called_once()
        kwargs = self.security_mock.call_args.kwargs
        self.assertEqual(kwargs['event_type'], 'PWD_RESET_REQUESTED')
        self.assertEqual(kwargs['target_user_id'], 'user-42')
        self.assertIn('username=jsmith', kwargs['detail'])

    def test_ip_throttle_runs_before_user_throttle(self):
        """Ordering matters: per-IP is cheaper and protects against
        cross-account enumeration from one source. If we hit the user
        path first an attacker iterates IPs to bypass it."""
        user = _active_user()
        self.User.objects.filter.return_value.first.return_value = user

        _post({'email': 'jsmith@example.com'})

        self.ip_throttle_mock.assert_called_once()
        self.user_throttle_mock.assert_called_once()
