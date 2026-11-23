"""Unit tests for MULTI_SESSIONS (one live client session when the flag is off)."""
from unittest import mock
from unittest.mock import MagicMock

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()
django.setup()

from django.test import SimpleTestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from core.auth.cookies import ACCESS_CLIENT_COOKIE, REFRESH_CLIENT_COOKIE
from core.errors import AppErrorCode, AuthException
from core.errors.codes import ERROR_REGISTRY
from client.features.security.lifecycle.auth.application.client_session import (
    IssueClientSessionUseCase,
    LogoutClientSessionUseCase,
)
from client.features.security.lifecycle.auth.application.session_policy import SessionPolicy
from client.features.security.lifecycle.auth.domain.schemas import AuthenticatedClient, IssuedClientSession
from core.access.billing_recovery import LoginAccessResult
from client.features.security.lifecycle.auth.presentation.api import (
    UserLoginAPIView,
    UserLogoutAPIView,
)

TestCase = SimpleTestCase

POLICY = 'client.features.security.lifecycle.auth.application.session_policy'
VIEW_PATH = 'client.features.security.lifecycle.auth.presentation.api'


class TestSessionExistsErrorRegistry(TestCase):

    def test_auth_018_is_409(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_SESSION_EXISTS]
        self.assertEqual(AppErrorCode.AUTH_SESSION_EXISTS.value, 'AUTH_018')
        self.assertEqual(entry['http_status'], 409)
        self.assertIn('session', entry['message'].lower())


class TestAllowsMultipleSessions(TestCase):

    def setUp(self):
        from client.features.security.lifecycle.auth.application import session_policy as policy
        self.policy = policy

    def test_inactive_or_false_disables_multi(self):
        for raw in (False, None, 0, ''):
            with mock.patch(f'{POLICY}.get_parameter', return_value=raw):
                self.assertFalse(self.policy.allows_multiple_sessions())

    def test_true_enables_multi(self):
        with mock.patch(f'{POLICY}.get_parameter', return_value=True):
            self.assertTrue(self.policy.allows_multiple_sessions())


class TestAssertCanOpenSession(TestCase):

    def setUp(self):
        self.tokens = MagicMock()
        self.tokens.list_for_user.return_value = []
        self.tokens.validate.return_value = None
        self.policy = SessionPolicy(self.tokens)

    def test_multi_on_never_blocks(self):
        self.tokens.list_for_user.return_value = [{'user_id': 'u1'}]
        with mock.patch(f'{POLICY}.get_parameter', return_value=True):
            self.policy.ensure_can_open_session('u1')

    def test_no_sessions_allows_login(self):
        with mock.patch(f'{POLICY}.get_parameter', return_value=False):
            self.policy.ensure_can_open_session('u1')

    def test_existing_session_blocks(self):
        self.tokens.list_for_user.return_value = [{'user_id': 'u1'}]
        with mock.patch(f'{POLICY}.get_parameter', return_value=False):
            with self.assertRaises(AuthException) as ctx:
                self.policy.ensure_can_open_session('u1')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_SESSION_EXISTS)
        self.assertEqual(ctx.exception.http_status, 409)

    def test_same_browser_refresh_is_allowed(self):
        self.tokens.list_for_user.return_value = [{'user_id': 'u1'}]
        self.tokens.validate.return_value = {'user_id': 'u1', 'user_type': 'client'}
        with mock.patch(f'{POLICY}.get_parameter', return_value=False):
            self.policy.ensure_can_open_session('u1', current_refresh_raw='rt-same')
        self.tokens.validate.assert_called_once_with('rt-same')

    def test_refresh_for_another_user_is_blocked(self):
        self.tokens.list_for_user.return_value = [{'user_id': 'u1'}]
        self.tokens.validate.return_value = {'user_id': 'other', 'user_type': 'client'}
        with mock.patch(f'{POLICY}.get_parameter', return_value=False):
            with self.assertRaises(AuthException) as ctx:
                self.policy.ensure_can_open_session('u1', current_refresh_raw='rt-other')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_SESSION_EXISTS)

    def test_listing_failure_fail_open(self):
        self.tokens.list_for_user.side_effect = RuntimeError('redis down')
        with mock.patch(f'{POLICY}.get_parameter', return_value=False):
            self.policy.ensure_can_open_session('u1')


class TestIssueClientSessionUseCase(TestCase):

    def setUp(self):
        self.tokens = MagicMock()
        self.tokens.generate_raw_token.return_value = 'raw-rt'
        self.tokens.store.return_value = ('raw-rt', 'sid123')
        self.auth = MagicMock()
        self.build = MagicMock()
        self.build.execute.return_value = MagicMock()
        self.policy = MagicMock()
        self.policy.allows_multiple_sessions.return_value = False
        self.use_case = IssueClientSessionUseCase(
            build_session=self.build,
            auth_repository=self.auth,
            tokens=self.tokens,
            policy=self.policy,
        )
        self.user = MagicMock(pk='u1', username='jsmith')

    def _execute(self, current_refresh_raw=None):
        return self.use_case.execute(
            self.user,
            current_refresh_raw=current_refresh_raw,
            schema_name='acme',
            ip='1.2.3.4',
            user_agent='test',
        )

    def test_single_session_revokes_all_then_stores(self):
        issued = self._execute()
        self.policy.ensure_can_open_session.assert_called_once()
        self.auth.touch_last_login.assert_called_once_with(self.user)
        self.tokens.revoke_all_for_user.assert_called_once_with('u1')
        self.tokens.revoke.assert_not_called()
        self.tokens.store.assert_called_once()
        store_kwargs = self.tokens.store.call_args.kwargs
        self.assertFalse(store_kwargs.get('remember_me'))
        self.assertIn('ttl_seconds', store_kwargs)
        self.assertIsInstance(issued, IssuedClientSession)
        self.assertEqual(issued.refresh_token, 'raw-rt')
        self.assertEqual(issued.session_id, 'sid123')
        self.assertEqual(issued.remember_me, False)

    def test_remember_me_uses_persistent_ttl(self):
        issued = self.use_case.execute(
            self.user,
            current_refresh_raw=None,
            schema_name='acme',
            ip='1.2.3.4',
            user_agent='test',
            remember_me=True,
        )
        store_kwargs = self.tokens.store.call_args.kwargs
        self.assertTrue(store_kwargs.get('remember_me'))
        self.assertTrue(issued.remember_me)

    def test_multi_session_keeps_other_sessions(self):
        self.policy.allows_multiple_sessions.return_value = True
        self._execute()
        self.tokens.revoke_all_for_user.assert_not_called()
        self.tokens.revoke.assert_not_called()
        self.tokens.store.assert_called_once()

    def test_multi_session_rotates_this_browser_only(self):
        self.policy.allows_multiple_sessions.return_value = True
        self._execute(current_refresh_raw='old-rt')
        self.tokens.revoke.assert_called_once_with('old-rt')
        self.tokens.revoke_all_for_user.assert_not_called()

    def test_existing_session_raises_before_issuing(self):
        self.policy.ensure_can_open_session.side_effect = AuthException(
            AppErrorCode.AUTH_SESSION_EXISTS,
        )
        with self.assertRaises(AuthException) as ctx:
            self._execute()
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_SESSION_EXISTS)
        self.tokens.store.assert_not_called()
        self.auth.touch_last_login.assert_not_called()


class TestLogoutClientSessionUseCase(TestCase):

    def setUp(self):
        self.tokens = MagicMock()
        self.policy = MagicMock()
        self.policy.allows_multiple_sessions.return_value = False
        self.use_case = LogoutClientSessionUseCase(
            tokens=self.tokens,
            policy=self.policy,
        )

    def test_single_session_revokes_all_for_user(self):
        self.use_case.execute(
            current_refresh_raw=None,
            access_user_id='u1',
            access_session_id='abc123',
        )
        self.tokens.revoke_all_for_user.assert_called_once_with('u1')
        self.tokens.revoke.assert_not_called()
        self.tokens.revoke_session.assert_not_called()

    def test_single_session_resolves_user_from_refresh(self):
        self.tokens.validate.return_value = {'user_id': 'u1'}
        self.use_case.execute(
            current_refresh_raw='raw-rt',
            access_user_id=None,
            access_session_id=None,
        )
        self.tokens.revoke_all_for_user.assert_called_once_with('u1')

    def test_multi_session_revokes_this_refresh_only(self):
        self.policy.allows_multiple_sessions.return_value = True
        self.use_case.execute(
            current_refresh_raw='raw-rt',
            access_user_id='u1',
            access_session_id='abc123',
        )
        self.tokens.revoke.assert_called_once_with('raw-rt')
        self.tokens.revoke_all_for_user.assert_not_called()
        self.tokens.revoke_session.assert_not_called()

    def test_multi_session_falls_back_to_access_sid(self):
        self.policy.allows_multiple_sessions.return_value = True
        self.use_case.execute(
            current_refresh_raw=None,
            access_user_id='u1',
            access_session_id='abc123',
        )
        self.tokens.revoke_session.assert_called_once_with('u1', 'abc123')
        self.tokens.revoke_all_for_user.assert_not_called()

    def test_multi_session_without_cookies_does_not_revoke_all(self):
        self.policy.allows_multiple_sessions.return_value = True
        self.use_case.execute(
            current_refresh_raw=None,
            access_user_id=None,
            access_session_id=None,
        )
        self.tokens.revoke_all_for_user.assert_not_called()
        self.tokens.revoke.assert_not_called()
        self.tokens.revoke_session.assert_not_called()


def _user(username='jsmith'):
    user = MagicMock()
    user.pk = 'user-pk'
    user.username = username
    return user


class TestLoginSessionGateBeforeTwoFactor(TestCase):

    def setUp(self):
        login_uc = mock.patch(f'{VIEW_PATH}.login_user_use_case')
        self.login_cls = login_uc.start()
        self.addCleanup(login_uc.stop)
        self.login_cls.return_value.execute.return_value = AuthenticatedClient(
            user=_user(), access=LoginAccessResult(mode='full'),
        )

        clock = mock.patch(f'{VIEW_PATH}.start_password_clock')
        clock.start()
        self.addCleanup(clock.stop)

        expired = mock.patch(f'{VIEW_PATH}.is_password_expired', return_value=False)
        expired.start()
        self.addCleanup(expired.stop)

        policy_fn = mock.patch(f'{VIEW_PATH}.session_policy')
        self.policy_fn = policy_fn.start()
        self.addCleanup(policy_fn.stop)
        self.gate = self.policy_fn.return_value.ensure_can_open_session
        self.gate.side_effect = AuthException(AppErrorCode.AUTH_SESSION_EXISTS)

        two_fa = mock.patch(f'{VIEW_PATH}.is_two_factor_enabled', return_value=True)
        two_fa.start()
        self.addCleanup(two_fa.stop)

        issue_otp = mock.patch(f'{VIEW_PATH}.IssueTwoFactorChallengeUseCase')
        self.issue_otp = issue_otp.start()
        self.addCleanup(issue_otp.stop)

        find = mock.patch(f'{VIEW_PATH}.FindTrustedDeviceUseCase')
        self.find = find.start()
        self.addCleanup(find.stop)

        session = mock.patch(f'{VIEW_PATH}._issue_client_session')
        self.issue_session = session.start()
        self.addCleanup(session.stop)
        self.issue_session.return_value = Response(status=200)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

    def test_existing_session_does_not_issue_2fa(self):
        request = APIRequestFactory().post(
            '/api/v1/auth/login/',
            {'username': 'jsmith', 'password': 'pass1234'},
            format='json',
        )
        response = UserLoginAPIView.as_view()(request)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['error']['code'], 'AUTH_018')
        self.gate.assert_called_once()
        self.find.return_value.execute.assert_not_called()
        self.issue_otp.return_value.execute.assert_not_called()
        self.issue_session.assert_not_called()


class TestLogoutSessionPolicy(TestCase):

    def setUp(self):
        logout_uc = mock.patch(f'{VIEW_PATH}.logout_client_session_use_case')
        self.logout_fn = logout_uc.start()
        self.addCleanup(logout_uc.stop)
        self.logout = self.logout_fn.return_value

        clear = mock.patch(f'{VIEW_PATH}.clear_auth_cookies', side_effect=lambda r, **k: r)
        clear.start()
        self.addCleanup(clear.stop)

    def _post(self, cookies=None):
        request = APIRequestFactory().post('/api/v1/auth/logout/', {}, format='json')
        request.COOKIES = cookies or {}
        return UserLogoutAPIView.as_view()(request)

    def test_logout_always_returns_204(self):
        response = self._post()
        self.assertEqual(response.status_code, 204)
        self.logout.execute.assert_called_once()

    def test_passes_refresh_cookie_to_use_case(self):
        response = self._post(cookies={REFRESH_CLIENT_COOKIE: 'raw-rt'})
        self.assertEqual(response.status_code, 204)
        kwargs = self.logout.execute.call_args.kwargs
        self.assertEqual(kwargs['current_refresh_raw'], 'raw-rt')

    def test_passes_access_claims_to_use_case(self):
        with mock.patch('jwt.decode', return_value={
            'user_type': 'client', 'user_id': 'u1', 'sid': 'abc123',
        }):
            response = self._post(cookies={ACCESS_CLIENT_COOKIE: 'access-jwt'})
        self.assertEqual(response.status_code, 204)
        kwargs = self.logout.execute.call_args.kwargs
        self.assertEqual(kwargs['access_user_id'], 'u1')
        self.assertEqual(kwargs['access_session_id'], 'abc123')
