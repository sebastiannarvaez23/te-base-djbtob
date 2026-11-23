"""Unit tests for UserLoginAPIView 2FA branching and verify/resend views."""
from unittest import mock
from unittest.mock import MagicMock

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()
django.setup()

from django.test import SimpleTestCase, override_settings
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from core.auth.cookies import DEVICE_CLIENT_COOKIE, DEVICE_COOKIE_MAX_AGE
from core.errors import AppErrorCode, AuthException, EmailNotVerifiedException
from client.features.security.lifecycle.auth.application.two_factor import hash_device
from client.features.security.lifecycle.auth.domain.schemas import (
    AuthenticatedClient,
    TrustedDeviceSchema,
    TwoFactorChallengeSchema,
    VerifiedTwoFactor,
)
from core.access.billing_recovery import LoginAccessResult
from client.features.security.lifecycle.auth.presentation.api import (
    ResendTwoFactorAPIView,
    TrustedDeviceListAPIView,
    TrustedDeviceRevokeAPIView,
    UserLoginAPIView,
    VerifyTwoFactorAPIView,
)

TestCase = SimpleTestCase
VIEW_PATH = 'client.features.security.lifecycle.auth.presentation.api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-2fa'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-2fa'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-2fa'},
}

DEVICE = 'a' * 32


def _user(username='jsmith'):
    user = MagicMock()
    user.pk = 'user-pk'
    user.username = username
    user.email = 'jsmith@base.local'
    user.first_name = 'Jane'
    user.last_name = 'Smith'
    return user


def _auth_result(user=None):
    user = user or _user()
    return AuthenticatedClient(user=user, access=LoginAccessResult(mode='full'))


@override_settings(CACHES=LOCMEM_CACHES)
class TestLoginTwoFactorBranch(TestCase):

    def setUp(self):
        login_uc = mock.patch(f'{VIEW_PATH}.login_user_use_case')
        self.login_cls = login_uc.start()
        self.addCleanup(login_uc.stop)
        self.login_cls.return_value.execute.return_value = _auth_result()

        flag = mock.patch(f'{VIEW_PATH}.is_two_factor_enabled', return_value=True)
        flag.start()
        self.addCleanup(flag.stop)

        find = mock.patch(f'{VIEW_PATH}.FindTrustedDeviceUseCase')
        self.find_cls = find.start()
        self.addCleanup(find.stop)

        issue = mock.patch(f'{VIEW_PATH}.IssueTwoFactorChallengeUseCase')
        self.issue_cls = issue.start()
        self.addCleanup(issue.stop)

        active = mock.patch(f'{VIEW_PATH}.GetActiveTwoFactorChallengeUseCase')
        self.active_cls = active.start()
        self.addCleanup(active.stop)
        self.active_cls.return_value.execute.return_value = None

        dispatch = mock.patch(f'{VIEW_PATH}._dispatch_2fa_email')
        self.dispatch = dispatch.start()
        self.addCleanup(dispatch.stop)

        session = mock.patch(f'{VIEW_PATH}._issue_client_session')
        self.issue_session = session.start()
        self.addCleanup(session.stop)
        self.issue_session.return_value = Response(status=200)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        policy = mock.patch(f'{VIEW_PATH}.session_policy')
        policy.start()
        self.addCleanup(policy.stop)

        clock = mock.patch(f'{VIEW_PATH}.start_password_clock')
        clock.start()
        self.addCleanup(clock.stop)

        expired = mock.patch(f'{VIEW_PATH}.is_password_expired', return_value=False)
        expired.start()
        self.addCleanup(expired.stop)

        slot = mock.patch(
            f'{VIEW_PATH}.try_acquire_two_factor_resend_slot', return_value=True,
        )
        self.resend_slot = slot.start()
        self.addCleanup(slot.stop)

    def _post(self, data):
        request = APIRequestFactory().post('/api/v1/auth/login/', data, format='json')
        return UserLoginAPIView.as_view()(request)

    def test_unknown_device_returns_challenge_without_session(self):
        self.find_cls.return_value.execute.return_value = None
        challenge = TwoFactorChallengeSchema(
            challenge_id='c' * 43,
            expires_in=300,
            email_hint='j***@base.local',
        )
        self.issue_cls.return_value.execute.return_value = ('482931', challenge)

        response = self._post({
            'username': 'jsmith', 'password': 'pass1234',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['data']['two_factor_required'])
        self.issue_session.assert_not_called()
        self.dispatch.assert_called_once()
        self.assertIsNone(self.find_cls.return_value.execute.call_args[0][1])

    def test_unverified_email_never_issues_2fa(self):
        self.login_cls.return_value.execute.side_effect = EmailNotVerifiedException(
            AppErrorCode.AUTH_EMAIL_NOT_VERIFIED,
            context={'user_id': 'user-pk'},
        )
        slot = mock.patch(f'{VIEW_PATH}.try_acquire_resend_slot', return_value=False)
        slot.start()
        self.addCleanup(slot.stop)

        response = self._post({
            'username': 'jsmith', 'password': 'pass1234',
        })

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'AUTH_007')
        self.issue_cls.return_value.execute.assert_not_called()
        self.active_cls.return_value.execute.assert_not_called()
        self.dispatch.assert_not_called()
        self.issue_session.assert_not_called()

    def test_body_device_id_is_rejected_as_unknown_field(self):
        response = self._post({
            'username': 'jsmith',
            'password': 'pass1234',
            'device_id': DEVICE,
        })

        self.assertEqual(response.status_code, 400)
        errors = response.data['errors']
        self.assertTrue(any(
            err['field'] == 'device_id' and err['code'] == 'UNKNOWN_FIELD'
            for err in errors
        ))
        self.login_cls.return_value.execute.assert_not_called()
        self.find_cls.return_value.execute.assert_not_called()

    def test_trusted_device_completes_login(self):
        self.find_cls.return_value.execute.return_value = MagicMock()
        touch = mock.patch(f'{VIEW_PATH}.TouchTrustedDeviceUseCase')
        touch.start()
        self.addCleanup(touch.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/login/',
            {'username': 'jsmith', 'password': 'pass1234'},
            format='json',
        )
        request.COOKIES = {DEVICE_CLIENT_COOKIE: DEVICE}
        UserLoginAPIView.as_view()(request)
        self.issue_session.assert_called_once()
        self.dispatch.assert_not_called()
        self.find_cls.return_value.execute.assert_called_once()
        self.assertEqual(self.find_cls.return_value.execute.call_args[0][1], DEVICE)

    def test_active_challenge_is_reused_when_resend_is_throttled(self):
        self.find_cls.return_value.execute.return_value = None
        self.resend_slot.return_value = False
        challenge = TwoFactorChallengeSchema(
            challenge_id='c' * 43,
            expires_in=200,
            email_hint='***@base.local',
        )
        self.active_cls.return_value.execute.return_value = challenge

        response = self._post({
            'username': 'jsmith', 'password': 'pass1234',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['data']['two_factor_required'])
        self.assertEqual(response.data['data']['challenge_id'], 'c' * 43)
        self.issue_cls.return_value.execute.assert_not_called()
        self.dispatch.assert_not_called()
        self.issue_session.assert_not_called()

    def test_login_retry_replaces_active_challenge_and_sends_new_email(self):
        self.find_cls.return_value.execute.return_value = None
        self.active_cls.return_value.execute.return_value = TwoFactorChallengeSchema(
            challenge_id='c' * 43,
            expires_in=200,
            email_hint='***@base.local',
        )
        replacement = TwoFactorChallengeSchema(
            challenge_id='d' * 43,
            expires_in=300,
            email_hint='***@base.local',
        )
        self.issue_cls.return_value.execute.return_value = ('111111', replacement)

        response = self._post({
            'username': 'jsmith', 'password': 'pass1234',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['data']['two_factor_required'])
        self.assertEqual(response.data['data']['challenge_id'], 'd' * 43)
        self.issue_cls.return_value.execute.assert_called_once()
        self.dispatch.assert_called_once()
        self.issue_session.assert_not_called()
        self.resend_slot.assert_called_once()


@override_settings(CACHES=LOCMEM_CACHES)
class TestLoginTwoFactorOff(TestCase):

    def test_flag_off_skips_challenge(self):
        login_uc = mock.patch(f'{VIEW_PATH}.login_user_use_case')
        login_cls = login_uc.start()
        self.addCleanup(login_uc.stop)
        login_cls.return_value.execute.return_value = _auth_result()

        flag = mock.patch(f'{VIEW_PATH}.is_two_factor_enabled', return_value=False)
        flag.start()
        self.addCleanup(flag.stop)

        session = mock.patch(f'{VIEW_PATH}._issue_client_session')
        issue_session = session.start()
        self.addCleanup(session.stop)
        issue_session.return_value = Response(status=200)

        policy = mock.patch(f'{VIEW_PATH}.session_policy')
        policy.start()
        self.addCleanup(policy.stop)

        clock = mock.patch(f'{VIEW_PATH}.start_password_clock')
        clock.start()
        self.addCleanup(clock.stop)

        expired = mock.patch(f'{VIEW_PATH}.is_password_expired', return_value=False)
        expired.start()
        self.addCleanup(expired.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/login/',
            {'username': 'jsmith', 'password': 'pass1234'},
            format='json',
        )
        UserLoginAPIView.as_view()(request)
        issue_session.assert_called_once()
        self.assertFalse(issue_session.call_args.kwargs.get('remember_me'))

    def test_remember_me_is_forwarded_to_session_issue(self):
        login_uc = mock.patch(f'{VIEW_PATH}.login_user_use_case')
        login_cls = login_uc.start()
        self.addCleanup(login_uc.stop)
        login_cls.return_value.execute.return_value = _auth_result()

        flag = mock.patch(f'{VIEW_PATH}.is_two_factor_enabled', return_value=False)
        flag.start()
        self.addCleanup(flag.stop)

        session = mock.patch(f'{VIEW_PATH}._issue_client_session')
        issue_session = session.start()
        self.addCleanup(session.stop)
        issue_session.return_value = Response(status=200)

        policy = mock.patch(f'{VIEW_PATH}.session_policy')
        policy.start()
        self.addCleanup(policy.stop)

        clock = mock.patch(f'{VIEW_PATH}.start_password_clock')
        clock.start()
        self.addCleanup(clock.stop)

        expired = mock.patch(f'{VIEW_PATH}.is_password_expired', return_value=False)
        expired.start()
        self.addCleanup(expired.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/login/',
            {'username': 'jsmith', 'password': 'pass1234', 'remember_me': True},
            format='json',
        )
        UserLoginAPIView.as_view()(request)
        issue_session.assert_called_once()
        self.assertTrue(issue_session.call_args.kwargs.get('remember_me'))


@override_settings(CACHES=LOCMEM_CACHES)
class TestVerifyTwoFactorView(TestCase):

    def test_valid_otp_registers_device_and_issues_session(self):
        verify = mock.patch(f'{VIEW_PATH}.VerifyTwoFactorChallengeUseCase')
        verify_cls = verify.start()
        self.addCleanup(verify.stop)
        user = _user()
        verify_cls.return_value.execute.return_value = VerifiedTwoFactor(user, True)

        register = mock.patch(f'{VIEW_PATH}.RegisterTrustedDeviceUseCase')
        register_cls = register.start()
        self.addCleanup(register.stop)

        session = mock.patch(f'{VIEW_PATH}._issue_client_session')
        issue_session = session.start()
        self.addCleanup(session.stop)
        issue_session.return_value = Response(status=200)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        gen = mock.patch(f'{VIEW_PATH}.generate_device_serial', return_value=DEVICE)
        gen.start()
        self.addCleanup(gen.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/login/verify-2fa/',
            {'challenge_id': 'c' * 43, 'otp_code': '482931', 'remember_device': True},
            format='json',
        )
        response = VerifyTwoFactorAPIView.as_view()(request)

        verify_cls.return_value.execute.assert_called_once()
        register_cls.return_value.execute.assert_called_once()
        issue_session.assert_called_once()
        self.assertTrue(issue_session.call_args.kwargs.get('remember_me'))
        cookie = response.cookies.get(DEVICE_CLIENT_COOKIE)
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, DEVICE)
        self.assertTrue(cookie['httponly'])
        self.assertEqual(int(cookie['max-age']), DEVICE_COOKIE_MAX_AGE)

    def test_valid_otp_without_remember_does_not_register_device(self):
        verify = mock.patch(f'{VIEW_PATH}.VerifyTwoFactorChallengeUseCase')
        verify_cls = verify.start()
        self.addCleanup(verify.stop)
        verify_cls.return_value.execute.return_value = VerifiedTwoFactor(_user(), False)

        register = mock.patch(f'{VIEW_PATH}.RegisterTrustedDeviceUseCase')
        register_cls = register.start()
        self.addCleanup(register.stop)

        session = mock.patch(f'{VIEW_PATH}._issue_client_session')
        issue_session = session.start()
        self.addCleanup(session.stop)
        issue_session.return_value = Response(status=200)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/login/verify-2fa/',
            {'challenge_id': 'c' * 43, 'otp_code': '482931'},
            format='json',
        )
        response = VerifyTwoFactorAPIView.as_view()(request)
        register_cls.return_value.execute.assert_not_called()
        issue_session.assert_called_once()
        self.assertFalse(issue_session.call_args.kwargs.get('remember_me'))
        self.assertIsNone(response.cookies.get(DEVICE_CLIENT_COOKIE))

    def test_invalid_otp_does_not_issue_session(self):
        verify = mock.patch(f'{VIEW_PATH}.VerifyTwoFactorChallengeUseCase')
        verify_cls = verify.start()
        self.addCleanup(verify.stop)
        verify_cls.return_value.execute.side_effect = AuthException(
            AppErrorCode.AUTH_OTP_INVALID,
        )

        session = mock.patch(f'{VIEW_PATH}._issue_client_session')
        issue_session = session.start()
        self.addCleanup(session.stop)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/login/verify-2fa/',
            {'challenge_id': 'c' * 43, 'otp_code': '000000'},
            format='json',
        )
        response = VerifyTwoFactorAPIView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        issue_session.assert_not_called()


@override_settings(CACHES=LOCMEM_CACHES)
class TestResendTwoFactorView(TestCase):

    def test_throttled_resend_does_not_rotate(self):
        peek = mock.patch(f'{VIEW_PATH}.PeekTwoFactorChallengeUseCase')
        peek_cls = peek.start()
        self.addCleanup(peek.stop)
        user = _user()
        challenge = TwoFactorChallengeSchema(
            challenge_id='c' * 43, expires_in=200, email_hint='j***@base.local',
        )
        peek_cls.return_value.execute.return_value = (user, challenge)

        slot = mock.patch(f'{VIEW_PATH}.try_acquire_two_factor_resend_slot', return_value=False)
        slot.start()
        self.addCleanup(slot.stop)

        rotate = mock.patch(f'{VIEW_PATH}.RotateTwoFactorChallengeUseCase')
        rotate_cls = rotate.start()
        self.addCleanup(rotate.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/login/resend-2fa/',
            {'challenge_id': 'c' * 43},
            format='json',
        )
        response = ResendTwoFactorAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        rotate_cls.return_value.execute.assert_not_called()

    def test_acquired_slot_rotates_and_dispatches(self):
        peek = mock.patch(f'{VIEW_PATH}.PeekTwoFactorChallengeUseCase')
        peek_cls = peek.start()
        self.addCleanup(peek.stop)
        user = _user()
        challenge = TwoFactorChallengeSchema(
            challenge_id='c' * 43, expires_in=200, email_hint='j***@base.local',
        )
        peek_cls.return_value.execute.return_value = (user, challenge)

        slot = mock.patch(f'{VIEW_PATH}.try_acquire_two_factor_resend_slot', return_value=True)
        slot.start()
        self.addCleanup(slot.stop)

        rotate = mock.patch(f'{VIEW_PATH}.RotateTwoFactorChallengeUseCase')
        rotate_cls = rotate.start()
        self.addCleanup(rotate.stop)
        rotated = TwoFactorChallengeSchema(
            challenge_id='c' * 43, expires_in=300, email_hint='j***@base.local',
        )
        rotate_cls.return_value.execute.return_value = (user, '482931', rotated)

        dispatch = mock.patch(f'{VIEW_PATH}._dispatch_2fa_email')
        dispatch_mock = dispatch.start()
        self.addCleanup(dispatch.stop)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/login/resend-2fa/',
            {'challenge_id': 'c' * 43},
            format='json',
        )
        response = ResendTwoFactorAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        rotate_cls.return_value.execute.assert_called_once_with('c' * 43)
        dispatch_mock.assert_called_once()
        self.assertTrue(response.data['data']['two_factor_required'])


@override_settings(CACHES=LOCMEM_CACHES)
class TestTrustedDeviceViews(TestCase):

    def test_list_returns_devices_and_passes_cookie_serial(self):
        list_uc = mock.patch(f'{VIEW_PATH}.ListTrustedDevicesUseCase')
        list_cls = list_uc.start()
        self.addCleanup(list_uc.stop)
        list_cls.return_value.execute.return_value = [
            TrustedDeviceSchema(
                id='11111111-1111-1111-1111-111111111111',
                label='Chrome - Windows',
                last_ip='1.1.1.1',
                last_used_at='2026-08-16T12:00:00+00:00',
                created_at='2026-08-01T12:00:00+00:00',
                is_current=True,
            ),
        ]

        user = _user()
        request = APIRequestFactory().get('/api/v1/auth/trusted-devices/')
        request.COOKIES = {DEVICE_CLIENT_COOKIE: DEVICE}
        force_authenticate(request, user=user)
        response = TrustedDeviceListAPIView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['data'][0]['is_current'])
        self.assertEqual(list_cls.return_value.execute.call_args[0][1], DEVICE)

    def test_revoke_current_device_clears_cookie(self):
        revoke_uc = mock.patch(f'{VIEW_PATH}.RevokeTrustedDeviceUseCase')
        revoke_cls = revoke_uc.start()
        self.addCleanup(revoke_uc.stop)
        user = _user()
        revoke_cls.return_value.execute.return_value = hash_device(user.pk, DEVICE)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        device_id = '11111111-1111-1111-1111-111111111111'
        request = APIRequestFactory().delete(f'/api/v1/auth/trusted-devices/{device_id}/')
        request.COOKIES = {DEVICE_CLIENT_COOKIE: DEVICE}
        force_authenticate(request, user=user)
        response = TrustedDeviceRevokeAPIView.as_view()(request, device_id=device_id)

        self.assertEqual(response.status_code, 204)
        cookie = response.cookies.get(DEVICE_CLIENT_COOKIE)
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie['max-age'], 0)

    def test_revoke_other_device_keeps_cookie(self):
        revoke_uc = mock.patch(f'{VIEW_PATH}.RevokeTrustedDeviceUseCase')
        revoke_cls = revoke_uc.start()
        self.addCleanup(revoke_uc.stop)
        revoke_cls.return_value.execute.return_value = 'other-device-hash'

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        device_id = '22222222-2222-2222-2222-222222222222'
        request = APIRequestFactory().delete(f'/api/v1/auth/trusted-devices/{device_id}/')
        request.COOKIES = {DEVICE_CLIENT_COOKIE: DEVICE}
        force_authenticate(request, user=_user())
        response = TrustedDeviceRevokeAPIView.as_view()(request, device_id=device_id)

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(response.cookies.get(DEVICE_CLIENT_COOKIE))

    def test_revoke_invalid_uuid_is_not_found(self):
        request = APIRequestFactory().delete('/api/v1/auth/trusted-devices/not-a-uuid/')
        force_authenticate(request, user=_user())
        response = TrustedDeviceRevokeAPIView.as_view()(request, device_id='not-a-uuid')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error']['code'], 'AUTH_014')
