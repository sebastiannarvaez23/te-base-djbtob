"""Unit tests for ResendConfirmationAPIView.

Behaviour checklist (see api.py docstring):

  * Always returns 204 regardless of lookup outcome — the response must
    not reveal whether an account exists (enumeration guard).
  * Input: exactly one of ``email`` / ``username`` is required; empty
    payload is a validation error, not a silent 204.
  * Email lookup is case-insensitive; username lookup falls through when
    email didn't match.
  * Already-verified users do not trigger a new token or dispatch.
  * Inactive users do not trigger a dispatch.
  * Throttle is acquired per-user; when not acquired, no token/email
    flows. The 204 response is identical either way (indistinguishable
    from the attacker's point of view).
  * Dispatch failures are swallowed so the response stays 204 — losing
    an email must not leak information.

Tests drive the view via ``APIRequestFactory`` and patch collaborators
at the view-module level. No database or Redis is needed.
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

TestCase = SimpleTestCase  # alias — avoids the DB setup that ``TestCase`` triggers

from client.features.security.lifecycle.auth.presentation.api import ResendConfirmationAPIView


VIEW_PATH = 'client.features.security.lifecycle.auth.presentation.api'

# django_redis is a deployment-only dep — override with LocMem so the view's
# transitive ``caches[...]`` lookups (auth middleware, error handler) resolve.
LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-t'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-t'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-t'},
}


def _post(data):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/auth/resend-confirmation/', data, format='json')
    return ResendConfirmationAPIView.as_view()(request)


def _active_unverified_user(pk='user-pk', username='jsmith', email='jsmith@example.com'):
    user = MagicMock()
    user.pk = pk
    user.username = username
    user.email = email
    user.email_verified_at = None
    user.is_active = True
    return user


@override_settings(CACHES=LOCMEM_CACHES)
class _ResendViewTestBase(TestCase):

    def setUp(self):
        self.User = MagicMock()
        user_patch = mock.patch(f'{VIEW_PATH}.get_user_model', return_value=self.User)
        user_patch.start()
        self.addCleanup(user_patch.stop)

        self.throttle = mock.patch(
            f'{VIEW_PATH}.try_acquire_resend_slot', return_value=True,
        )
        self.throttle_mock = self.throttle.start()
        self.addCleanup(self.throttle.stop)

        self.dispatch = mock.patch(f'{VIEW_PATH}._issue_and_dispatch_confirmation')
        self.dispatch_mock = self.dispatch.start()
        self.addCleanup(self.dispatch.stop)


class TestValidation(_ResendViewTestBase):

    def test_empty_body_is_400(self):
        """Without either identifier we have nothing to look up — the view
        surfaces a validation error instead of silently 204-ing, since this
        is a client bug, not an enumeration surface."""
        response = _post({})
        self.assertEqual(response.status_code, 400)

    def test_invalid_email_format_is_400(self):
        response = _post({'email': 'not-an-email'})
        self.assertEqual(response.status_code, 400)

    def test_username_too_short_is_400(self):
        response = _post({'username': 'ab'})
        self.assertEqual(response.status_code, 400)


class TestEnumerationSafety(_ResendViewTestBase):

    def test_unknown_email_returns_204(self):
        """Attackers cannot distinguish known-but-unverified vs unknown."""
        self.User.objects.filter.return_value.first.return_value = None

        response = _post({'email': 'ghost@example.com'})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.dispatch_mock.assert_not_called()

    def test_unknown_username_returns_204(self):
        self.User.objects.filter.return_value.first.return_value = None

        response = _post({'username': 'ghost'})

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.dispatch_mock.assert_not_called()

    def test_already_verified_user_returns_204_without_dispatch(self):
        user = _active_unverified_user()
        user.email_verified_at = MagicMock()  # verified
        self.User.objects.filter.return_value.first.return_value = user

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_not_called()

    def test_inactive_user_returns_204_without_dispatch(self):
        user = _active_unverified_user()
        user.is_active = False
        self.User.objects.filter.return_value.first.return_value = user

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_not_called()

    def test_throttled_user_returns_204_without_dispatch(self):
        """Throttle-block must not reveal itself via response body or status —
        an attacker polling resend for a target email can't tell whether the
        slot is taken (account exists) or the lookup missed."""
        self.throttle_mock.return_value = False
        user = _active_unverified_user()
        self.User.objects.filter.return_value.first.return_value = user

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_not_called()

    def test_user_lookup_exception_returns_204(self):
        """A transient DB failure during lookup must degrade to 204 so an
        attacker cannot probe infra state via 500s — the view logs the error
        and moves on."""
        self.User.objects.filter.side_effect = RuntimeError('db down')

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_not_called()

    def test_dispatch_exception_is_swallowed(self):
        """If SMTP is down we still return 204 — the client has nothing
        actionable and a 500 would leak that the account exists."""
        user = _active_unverified_user()
        self.User.objects.filter.return_value.first.return_value = user
        self.dispatch_mock.side_effect = RuntimeError('smtp down')

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)


class TestLookupStrategy(_ResendViewTestBase):

    def test_email_lookup_is_case_insensitive(self):
        """Users type their email with inconsistent casing — iexact avoids
        locking out a valid resend because the capitalisation differs from
        signup."""
        user = _active_unverified_user()
        self.User.objects.filter.return_value.first.return_value = user

        _post({'email': 'JSmith@Example.com'})

        # The view passes email__iexact=email; assert the kwarg.
        kwargs = self.User.objects.filter.call_args.kwargs
        self.assertIn('email__iexact', kwargs)
        self.assertEqual(kwargs['email__iexact'], 'JSmith@Example.com')

    def test_username_is_tried_when_email_missing(self):
        user = _active_unverified_user()
        self.User.objects.filter.return_value.first.return_value = user

        _post({'username': 'jsmith'})

        kwargs = self.User.objects.filter.call_args.kwargs
        self.assertEqual(kwargs.get('username'), 'jsmith')

    def test_both_fields_present_prefers_email_then_username(self):
        """If the email match returns None we must fall through to username
        before giving up — covers resend forms that pre-fill both."""
        first_call = MagicMock()
        first_call.first.return_value = None  # email miss
        second_call = MagicMock()
        second_call.first.return_value = _active_unverified_user()  # username hit
        self.User.objects.filter.side_effect = [first_call, second_call]

        response = _post({'email': 'ghost@example.com', 'username': 'jsmith'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_called_once()
        # First lookup was by email, second by username.
        email_kwargs = self.User.objects.filter.call_args_list[0].kwargs
        username_kwargs = self.User.objects.filter.call_args_list[1].kwargs
        self.assertIn('email__iexact', email_kwargs)
        self.assertIn('username', username_kwargs)

    def test_username_whitespace_is_trimmed(self):
        """The view defensively strips identifiers — a defense against UIs
        that leak trailing whitespace from copy-paste. Exercised on username
        because the email validator already rejects whitespace earlier."""
        user = _active_unverified_user()
        self.User.objects.filter.return_value.first.return_value = user

        _post({'username': '  jsmith  '})

        kwargs = self.User.objects.filter.call_args.kwargs
        self.assertEqual(kwargs['username'], 'jsmith')


class TestHappyPath(_ResendViewTestBase):

    def test_active_unverified_user_triggers_dispatch(self):
        user = _active_unverified_user()
        self.User.objects.filter.return_value.first.return_value = user

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        self.dispatch_mock.assert_called_once_with(user)

    def test_throttle_is_acquired_with_user_pk(self):
        """The throttle key must be per-user so separate accounts can
        resend independently."""
        user = _active_unverified_user(pk='user-42')
        self.User.objects.filter.return_value.first.return_value = user

        _post({'email': 'jsmith@example.com'})

        self.throttle_mock.assert_called_once_with('user-42')

    def test_response_has_no_body(self):
        """204 responses must have an empty body — security_log data must
        never leak into the payload."""
        user = _active_unverified_user()
        self.User.objects.filter.return_value.first.return_value = user

        response = _post({'email': 'jsmith@example.com'})

        self.assertEqual(response.status_code, 204)
        # DRF Response with no data serialises to b''.
        self.assertIn(getattr(response, 'data', None), (None, '', b''))
