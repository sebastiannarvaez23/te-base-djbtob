"""Unit tests for admin login authentication scenarios (JWT + refresh token).

Tests cover:
  - Successful admin login (repository-level)
  - Invalid credentials (wrong password)
  - Non-existent admin user
  - Inactive admin user
  - AdminLoginUseCase returns user or None
  - JWTAdminAccessAuthentication via the AdminTokenAuthentication shim
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors import AppErrorCode
from core.errors.codes import ERROR_REGISTRY


# ── Helpers ────────────────────────────────────────────────────────────────────

def _admin_user(username='admin1', is_active=True, password_valid=True):
    user = MagicMock()
    user.pk = uuid.uuid4()
    user.id = user.pk
    user.username = username
    user.is_active = is_active
    user.check_password = MagicMock(return_value=password_valid)
    return user


# ── Admin repository: successful login ───────────────────────────────────────

class TestAdminLoginSuccess(TestCase):

    @patch('platform.features.security.auth.auth.infrastructure.repositories.AdminUser')
    def test_valid_credentials_returns_user(self, MockAdminUser):
        from platform.features.security.auth.auth.infrastructure.repositories import DjangoAdminAuthRepository

        user = _admin_user(username='admin1', password_valid=True)
        MockAdminUser.objects.select_related.return_value.get.return_value = user

        repo = DjangoAdminAuthRepository()
        result = repo.authenticate('admin1', 'correctpass')

        self.assertIsNotNone(result)
        self.assertEqual(result.username, 'admin1')
        user.check_password.assert_called_once_with('correctpass')

    @patch('platform.features.security.auth.auth.infrastructure.repositories.AdminUser')
    def test_authenticate_does_not_stamp_last_login(self, MockAdminUser):
        """last_login is stamped only after a full session is issued (post-2FA)."""
        from platform.features.security.auth.auth.infrastructure.repositories import DjangoAdminAuthRepository

        user = _admin_user(password_valid=True)
        MockAdminUser.objects.select_related.return_value.get.return_value = user

        repo = DjangoAdminAuthRepository()
        repo.authenticate('admin1', 'pass1234')

        user.save.assert_not_called()

    @patch('platform.features.security.auth.auth.infrastructure.repositories.AdminUser')
    def test_touch_last_login_updates_timestamp(self, MockAdminUser):
        from platform.features.security.auth.auth.infrastructure.repositories import DjangoAdminAuthRepository

        user = _admin_user(password_valid=True)
        repo = DjangoAdminAuthRepository()
        repo.touch_last_login(user)

        user.save.assert_called_once_with(update_fields=['last_login'])


# ── Admin repository: invalid credentials ────────────────────────────────────

class TestAdminLoginInvalidCredentials(TestCase):

    @patch('platform.features.security.auth.auth.infrastructure.repositories.AdminUser')
    def test_wrong_password_returns_none(self, MockAdminUser):
        from platform.features.security.auth.auth.infrastructure.repositories import DjangoAdminAuthRepository

        user = _admin_user(password_valid=False)
        MockAdminUser.objects.select_related.return_value.get.return_value = user

        repo = DjangoAdminAuthRepository()
        result = repo.authenticate('admin1', 'wrongpassword')

        self.assertIsNone(result)

    @patch('platform.features.security.auth.auth.infrastructure.repositories.AdminUser')
    def test_wrong_password_does_not_update_last_login(self, MockAdminUser):
        from platform.features.security.auth.auth.infrastructure.repositories import DjangoAdminAuthRepository

        user = _admin_user(password_valid=False)
        MockAdminUser.objects.select_related.return_value.get.return_value = user

        repo = DjangoAdminAuthRepository()
        repo.authenticate('admin1', 'wrong')

        user.save.assert_not_called()


# ── Admin repository: non-existent user ──────────────────────────────────────

class TestAdminLoginUserNotFound(TestCase):

    @patch('platform.features.security.auth.auth.infrastructure.repositories.AdminUser')
    def test_nonexistent_user_returns_none(self, MockAdminUser):
        from platform.features.security.auth.auth.infrastructure.repositories import DjangoAdminAuthRepository

        MockAdminUser.DoesNotExist = Exception
        MockAdminUser.objects.select_related.return_value.get.side_effect = MockAdminUser.DoesNotExist()

        repo = DjangoAdminAuthRepository()
        result = repo.authenticate('ghost', 'pass1234')

        self.assertIsNone(result)


# ── Admin repository: inactive user ─────────────────────────────────────────

class TestAdminLoginInactiveUser(TestCase):

    @patch('platform.features.security.auth.auth.infrastructure.repositories.AdminUser')
    def test_inactive_admin_not_found_by_query(self, MockAdminUser):
        from platform.features.security.auth.auth.infrastructure.repositories import DjangoAdminAuthRepository

        MockAdminUser.DoesNotExist = Exception
        MockAdminUser.objects.select_related.return_value.get.side_effect = MockAdminUser.DoesNotExist()

        repo = DjangoAdminAuthRepository()
        result = repo.authenticate('inactive_admin', 'pass1234')

        self.assertIsNone(result)


# ── Admin use case ───────────────────────────────────────────────────────────

class TestAdminLoginUseCase(TestCase):

    def test_returns_none_on_invalid_credentials(self):
        from platform.features.security.auth.auth.application.use_cases import AdminLoginUseCase

        mock_repo = MagicMock()
        mock_repo.authenticate.return_value = None
        uc = AdminLoginUseCase(mock_repo)

        result = uc.execute('admin', 'wrong')
        self.assertIsNone(result)

    def test_returns_user_on_success(self):
        from platform.features.security.auth.auth.application.use_cases import AdminLoginUseCase

        mock_repo = MagicMock()
        user = _admin_user()
        mock_repo.authenticate.return_value = user
        uc = AdminLoginUseCase(mock_repo)

        result = uc.execute('admin1', 'pass1234')
        self.assertEqual(result, user)


# ── AdminTokenAuthentication (JWT-based shim) ────────────────────────────────

class TestAdminTokenAuthentication(TestCase):

    def setUp(self):
        from platform.core.authentication import AdminTokenAuthentication
        self.auth = AdminTokenAuthentication()

    def test_missing_cookie_returns_none(self):
        request = MagicMock()
        request.COOKIES = {}

        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_expired_token_raises_authentication_failed(self, mock_decode):
        import jwt as pyjwt
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.side_effect = pyjwt.ExpiredSignatureError()
        request = MagicMock()
        request.COOKIES = {'access_admin': 'expired-jwt'}

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_invalid_token_raises_authentication_failed(self, mock_decode):
        import jwt as pyjwt
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.side_effect = pyjwt.InvalidTokenError()
        request = MagicMock()
        request.COOKIES = {'access_admin': 'bad-jwt'}

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)


# ── Auth error codes validation ──────────────────────────────────────────────

class TestAuthErrorCodes(TestCase):

    def test_auth_001_invalid_credentials(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_INVALID_CREDENTIALS]
        self.assertEqual(entry['http_status'], 401)
        self.assertEqual(AppErrorCode.AUTH_INVALID_CREDENTIALS.value, 'AUTH_001')

    def test_auth_002_role_disabled(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_ROLE_DISABLED]
        self.assertEqual(entry['http_status'], 403)

    def test_auth_003_account_inactive(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_ACCOUNT_INACTIVE]
        self.assertEqual(entry['http_status'], 403)

    def test_auth_004_token_invalid(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_TOKEN_INVALID]
        self.assertEqual(entry['http_status'], 401)

    def test_auth_006_company_suspended(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_COMPANY_SUSPENDED]
        self.assertEqual(entry['http_status'], 403)
