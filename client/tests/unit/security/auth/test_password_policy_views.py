"""Unit tests for password-expiry login gate and change-password view."""
from unittest import mock
from unittest.mock import MagicMock

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()
django.setup()

from django.test import SimpleTestCase, override_settings
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from core.errors import AppErrorCode, AuthException
from client.features.security.lifecycle.auth.presentation.api import (
    ChangePasswordAPIView,
    UserLoginAPIView,
)

TestCase = SimpleTestCase
VIEW_PATH = 'client.features.security.lifecycle.auth.presentation.api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-pwdpol'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-pwdpol'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-pwdpol'},
}


def _user(username='jsmith'):
    user = MagicMock()
    user.pk = 'user-pk'
    user.username = username
    return user


@override_settings(CACHES=LOCMEM_CACHES)
class TestLoginPasswordExpired(TestCase):

    def setUp(self):
        login_uc = mock.patch(f'{VIEW_PATH}.login_user_use_case')
        self.login_cls = login_uc.start()
        self.addCleanup(login_uc.stop)
        self.login_cls.return_value.execute.return_value = _user()

        expired = mock.patch(f'{VIEW_PATH}.is_password_expired', return_value=True)
        self.expired = expired.start()
        self.addCleanup(expired.stop)

        issue = mock.patch(f'{VIEW_PATH}.IssueTwoFactorChallengeUseCase')
        self.issue_cls = issue.start()
        self.addCleanup(issue.stop)

        session = mock.patch(f'{VIEW_PATH}._issue_client_session')
        self.issue_session = session.start()
        self.addCleanup(session.stop)
        self.issue_session.return_value = Response(status=200)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

    def test_expired_password_blocks_session_and_2fa(self):
        request = APIRequestFactory().post(
            '/api/v1/auth/login/',
            {'username': 'jsmith', 'password': 'pass1234'},
            format='json',
        )
        response = UserLoginAPIView.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'AUTH_015')
        self.issue_session.assert_not_called()
        self.issue_cls.return_value.execute.assert_not_called()


@override_settings(CACHES=LOCMEM_CACHES)
class TestChangePasswordView(TestCase):

    def test_valid_current_password_rotates_without_session(self):
        login_uc = mock.patch(f'{VIEW_PATH}.login_user_use_case')
        login_cls = login_uc.start()
        self.addCleanup(login_uc.stop)
        user = _user()
        from client.features.security.lifecycle.auth.domain.schemas import AuthenticatedClient
        from core.access.billing_recovery import LoginAccessResult
        login_cls.return_value.execute.return_value = AuthenticatedClient(
            user=user, access=LoginAccessResult(mode='full'),
        )

        rotate = mock.patch(f'{VIEW_PATH}.rotate_password')
        rotate_mock = rotate.start()
        self.addCleanup(rotate.stop)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/password/change/',
            {
                'username': 'jsmith',
                'current_password': 'pass1234',
                'new_password': 'BrandNew456',
            },
            format='json',
        )
        response = ChangePasswordAPIView.as_view()(request)
        self.assertEqual(response.status_code, 204)
        rotate_mock.assert_called_once_with(user, 'BrandNew456')

    def test_reused_password_does_not_look_like_success(self):
        login_uc = mock.patch(f'{VIEW_PATH}.login_user_use_case')
        login_cls = login_uc.start()
        self.addCleanup(login_uc.stop)
        login_cls.return_value.execute.return_value = _user()

        rotate = mock.patch(f'{VIEW_PATH}.rotate_password')
        rotate_mock = rotate.start()
        self.addCleanup(rotate.stop)
        rotate_mock.side_effect = AuthException(AppErrorCode.AUTH_PASSWORD_REUSED)

        slog = mock.patch(f'{VIEW_PATH}.security_log')
        slog.start()
        self.addCleanup(slog.stop)

        request = APIRequestFactory().post(
            '/api/v1/auth/password/change/',
            {
                'username': 'jsmith',
                'current_password': 'pass1234',
                'new_password': 'pass1234',
            },
            format='json',
        )
        response = ChangePasswordAPIView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'AUTH_016')
