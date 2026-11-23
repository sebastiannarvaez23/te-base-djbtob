"""Unit tests for admin auth policies driven by admin parameters."""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors.codes import AppErrorCode
from core.errors.exceptions import AuthException
from platform.features.security.auth.auth.application.admin_session import (
    IssueAdminSessionUseCase,
    LogoutAdminSessionUseCase,
)
from platform.features.security.auth.auth.application.login_lockout import (
    AdminLoginLockout,
    max_retries,
)
from platform.features.security.auth.auth.application.password_policy import (
    history_limit,
    is_password_expired,
)
from platform.features.security.auth.auth.application.session_policy import (
    AdminSessionPolicy,
    allows_multiple_sessions,
)
from platform.features.security.auth.auth.application.two_factor import (
    IssueAdminTwoFactorChallengeUseCase,
    VerifyAdminTwoFactorChallengeUseCase,
    hash_otp,
    is_two_factor_enabled,
)


class TestAdminMaxRetries(TestCase):

    @patch('platform.features.security.auth.auth.application.login_lockout.get_admin_parameter', return_value=3)
    def test_reads_admin_catalog(self, mock_get):
        self.assertEqual(max_retries(), 3)
        mock_get.assert_called_once_with('MAX_LOGIN_RETRIES', default=0)

    @patch('platform.features.security.auth.auth.application.login_lockout.get_admin_parameter', return_value=0)
    def test_zero_disables(self, _mock):
        self.assertEqual(max_retries(), 0)


class TestAdminLoginLockout(TestCase):

    @patch('platform.features.security.auth.auth.application.login_lockout.max_retries', return_value=2)
    def test_locks_when_ceiling_hit(self, _max):
        store = MagicMock()
        store.get_failures.return_value = 2
        store.ttl_remaining.return_value = 60
        with self.assertRaises(AuthException) as ctx:
            AdminLoginLockout(store).assert_not_locked('admin')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_LOGIN_LOCKED)

    @patch('platform.features.security.auth.auth.application.login_lockout.max_retries', return_value=3)
    def test_fail_closed_on_store_error(self, _max):
        store = MagicMock()
        store.get_failures.side_effect = RuntimeError('redis down')
        with self.assertRaises(AuthException) as ctx:
            AdminLoginLockout(store).assert_not_locked('admin')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_LOGIN_LOCKED)


class TestAdminSessionPolicy(TestCase):

    @patch(
        'platform.features.security.auth.auth.application.session_policy.get_admin_parameter',
        return_value=True,
    )
    def test_allows_multiple(self, mock_get):
        self.assertTrue(allows_multiple_sessions())
        mock_get.assert_called_once_with('MULTI_SESSIONS', default=False)

    @patch(
        'platform.features.security.auth.auth.application.session_policy.get_admin_parameter',
        return_value=False,
    )
    @patch('platform.features.security.auth.auth.application.session_policy.refresh_service')
    def test_rejects_when_session_exists(self, mock_refresh, _param):
        mock_refresh.list_for_user.return_value = [{'user_id': 'u1'}]
        with self.assertRaises(AuthException) as ctx:
            AdminSessionPolicy().ensure_can_open_session('u1')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_SESSION_EXISTS)

    @patch(
        'platform.features.security.auth.auth.application.session_policy.get_admin_parameter',
        return_value=False,
    )
    @patch('platform.features.security.auth.auth.application.session_policy.refresh_service')
    def test_fail_closed_on_list_error(self, mock_refresh, _param):
        mock_refresh.list_for_user.side_effect = RuntimeError('redis down')
        with self.assertRaises(AuthException) as ctx:
            AdminSessionPolicy().ensure_can_open_session('u1')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_SESSION_EXISTS)


class TestIssueAdminSessionUseCase(TestCase):

    @patch('platform.features.security.auth.auth.application.admin_session.start_password_clock')
    @patch('platform.features.security.auth.auth.application.admin_session.create_access_token', return_value='access')
    @patch('platform.features.security.auth.auth.application.admin_session.refresh_service')
    def test_revokes_all_when_multi_off(self, mock_refresh, _access, _clock):
        mock_refresh.generate_raw_token.return_value = 'raw'
        mock_refresh.store.return_value = ({}, 'sid-1')
        auth_repo = MagicMock()
        policy = MagicMock()
        policy.allows_multiple_sessions.return_value = False
        user = MagicMock(pk='u1', username='admin')
        IssueAdminSessionUseCase(auth_repository=auth_repo, policy=policy).execute(
            user, current_refresh_raw='old', ip='1.1.1.1', user_agent='ua',
        )
        mock_refresh.revoke_all_for_user.assert_called_once_with('u1', user_type='admin')
        mock_refresh.revoke_others_for_user.assert_called_once_with(
            'u1', 'admin', keep_token_id='sid-1',
        )
        mock_refresh.revoke.assert_not_called()
        auth_repo.touch_last_login.assert_called_once_with(user)

    @patch('platform.features.security.auth.auth.application.admin_session.start_password_clock')
    @patch('platform.features.security.auth.auth.application.admin_session.create_access_token', return_value='access')
    @patch('platform.features.security.auth.auth.application.admin_session.refresh_service')
    def test_revokes_current_when_multi_on(self, mock_refresh, _access, _clock):
        mock_refresh.generate_raw_token.return_value = 'raw'
        mock_refresh.store.return_value = ({}, 'sid-1')
        auth_repo = MagicMock()
        policy = MagicMock()
        policy.allows_multiple_sessions.return_value = True
        user = MagicMock(pk='u1', username='admin')
        IssueAdminSessionUseCase(auth_repository=auth_repo, policy=policy).execute(
            user, current_refresh_raw='old',
        )
        mock_refresh.revoke.assert_called_once_with('old', user_type='admin')
        mock_refresh.revoke_all_for_user.assert_not_called()
        mock_refresh.revoke_others_for_user.assert_not_called()


class TestLogoutAdminSessionUseCase(TestCase):

    @patch('platform.features.security.auth.auth.application.admin_session.refresh_service')
    def test_multi_on_revokes_current_only(self, mock_refresh):
        policy = MagicMock()
        policy.allows_multiple_sessions.return_value = True
        LogoutAdminSessionUseCase(policy=policy).execute(
            current_refresh_raw='raw',
            access_user_id='u1',
            access_session_id='sid',
        )
        mock_refresh.revoke.assert_called_once_with('raw', user_type='admin')
        mock_refresh.revoke_all_for_user.assert_not_called()

    @patch('platform.features.security.auth.auth.application.admin_session.refresh_service')
    def test_multi_off_revokes_all(self, mock_refresh):
        policy = MagicMock()
        policy.allows_multiple_sessions.return_value = False
        LogoutAdminSessionUseCase(policy=policy).execute(
            current_refresh_raw=None,
            access_user_id='u1',
        )
        mock_refresh.revoke_all_for_user.assert_called_once_with('u1', user_type='admin')


class TestAdminPasswordPolicy(TestCase):

    @patch('platform.features.security.auth.auth.application.password_policy.get_admin_parameter', return_value=5)
    def test_history_limit(self, mock_get):
        self.assertEqual(history_limit(), 5)
        mock_get.assert_called_with('HISTORY_PASS', default=0)

    @patch('platform.features.security.auth.auth.application.password_policy.expiry_days', return_value=0)
    def test_expiry_disabled(self, _days):
        user = MagicMock(password_changed_at=None)
        self.assertFalse(is_password_expired(user))

    @patch(
        'platform.features.security.auth.auth.application.password_policy.transaction.atomic',
        lambda fn=None: (fn if callable(fn) else MagicMock()),
    )
    @patch(
        'platform.features.security.auth.auth.application.password_policy._usable_hash',
        return_value=True,
    )
    @patch(
        'platform.features.security.auth.auth.application.password_policy.check_password',
        return_value=True,
    )
    def test_rejects_same_as_current(self, _check, _usable):
        # Bypass @transaction.atomic DB entry; reuse check is pure.
        from platform.features.security.auth.auth.application import password_policy as pp

        def _plain_rotate(user, new_password, *, save=True):
            if pp._usable_hash(user) and pp.check_password(new_password, user.password):
                raise AuthException(AppErrorCode.AUTH_PASSWORD_REUSED)

        user = MagicMock(pk='u1', password='hash')
        with self.assertRaises(AuthException) as ctx:
            _plain_rotate(user, 'SamePass1!', save=False)
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_PASSWORD_REUSED)


class TestAdminTwoFactor(TestCase):

    @patch('platform.features.security.auth.auth.application.two_factor.get_admin_parameter', return_value=True)
    def test_enabled_from_admin_catalog(self, mock_get):
        self.assertTrue(is_two_factor_enabled())
        mock_get.assert_called_once_with('DOUBLE_FA_AUTH', default=False)

    @patch('platform.features.security.auth.auth.application.two_factor.two_factor_store')
    def test_issue_and_verify_otp(self, mock_store):
        user = MagicMock(pk='u1', email='a@example.com', is_active=True)
        otp, challenge = IssueAdminTwoFactorChallengeUseCase().execute(
            user, ip='10.0.0.1',
        )
        self.assertTrue(challenge.two_factor_required)
        self.assertEqual(len(otp), 6)
        payload = mock_store.replace_for_user.call_args.args[3]
        mock_store.get.return_value = payload
        users = MagicMock()
        users.get_active_by_id.return_value = user
        verified = VerifyAdminTwoFactorChallengeUseCase(users).execute(
            challenge.challenge_id, otp, ip='10.0.0.1',
        )
        self.assertIs(verified.user, user)
        mock_store.delete.assert_called_with(challenge.challenge_id)
        mock_store.incr_attempts.assert_not_called()
        self.assertEqual(
            hash_otp(challenge.challenge_id, otp),
            payload['otp_hash'],
        )

    @patch('platform.features.security.auth.auth.application.two_factor.two_factor_store')
    def test_verify_rejects_ip_mismatch(self, mock_store):
        from django.utils import timezone
        from datetime import timedelta
        user = MagicMock(pk='u1', email='a@example.com', is_active=True)
        otp, challenge = IssueAdminTwoFactorChallengeUseCase().execute(
            user, ip='10.0.0.1',
        )
        payload = mock_store.replace_for_user.call_args.args[3]
        payload['expires_at'] = (timezone.now() + timedelta(minutes=5)).isoformat()
        mock_store.get.return_value = payload
        users = MagicMock()
        with self.assertRaises(AuthException) as ctx:
            VerifyAdminTwoFactorChallengeUseCase(users).execute(
                challenge.challenge_id, otp, ip='10.0.0.9',
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_EXPIRED)
        mock_store.delete.assert_called_with(challenge.challenge_id)


class TestAdminTokenTtlIsolation(TestCase):

    @patch('core.admin_parameters.get_admin_parameter', return_value=15)
    def test_admin_access_ttl_uses_admin_catalog(self, mock_admin):
        from core.auth.jwt_service import get_access_ttl_minutes
        with patch('core.parameters.get_parameter') as client_get:
            self.assertEqual(get_access_ttl_minutes('admin'), 15)
            client_get.assert_not_called()
        mock_admin.assert_called_with('TOKEN_DURATION', default=None)

    @patch('core.parameters.get_parameter', return_value=20)
    def test_client_access_ttl_uses_parameter_facade(self, mock_client):
        from core.auth.jwt_service import get_access_ttl_minutes
        self.assertEqual(get_access_ttl_minutes('client'), 20)
        mock_client.assert_called_with('TOKEN_DURATION', default=None)

    @patch('core.admin_parameters.get_admin_parameter', return_value=7)
    def test_admin_refresh_ttl_uses_admin_catalog(self, mock_admin):
        from core.auth.refresh_service import get_refresh_ttl_days
        with patch('core.parameters.get_parameter') as client_get:
            self.assertEqual(get_refresh_ttl_days('admin'), 7)
            client_get.assert_not_called()
        mock_admin.assert_called_with('REF_TOKEN_DURATION', default=None)
