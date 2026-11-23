"""
Unit tests for client login authentication scenarios:
  - Successful login with valid credentials
  - Invalid credentials (wrong password)
  - Non-existent user (username not found)
  - Inactive user (is_active=False)
  - Disabled role (rol.is_active=False)
  - Suspended company (no active CompanySubscription)
  - Correct error codes and HTTP statuses for each scenario

Tests the repository-level logic (DjangoAuthRepository.authenticate)
using mocked ORM objects. No database required.
"""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch, PropertyMock

from core.errors import AppErrorCode, AuthException
from core.errors.codes import ERROR_REGISTRY


# ── Helpers ────────────────────────────────────────────────────────────────────

def _user_orm(
    username='jsmith',
    is_active=True,
    password_valid=True,
    role_active=True,
    role_name='Operador',
    has_role=True,
):
    """Creates a mock User ORM object with related company and role."""
    user = MagicMock()
    user.pk = uuid.uuid4()
    user.id = user.pk
    user.username = username
    user.is_active = is_active
    user.check_password = MagicMock(return_value=password_valid)

    if has_role:
        role = MagicMock()
        role.name = role_name
        role.is_active = role_active
        user.rol = role
    else:
        user.rol = None

    company = MagicMock()
    company.id = uuid.uuid4()
    company.name = 'Empresa Test'
    company.lifecycle = 'ACTIVE'
    user.company = company

    return user


def _active_subscription(*, plan_active=True):
    """Creates a mock CompanySubscription with ACTIVE status."""
    cs = MagicMock()
    cs.status = 'active'
    plan = MagicMock()
    plan.is_active = plan_active
    cs.subscription = plan
    return cs


def _inactive_subscription():
    """Creates a mock CompanySubscription with CANCELLED status."""
    cs = MagicMock()
    cs.status = 'cancelled'
    return cs


def _stub_latest_acquisition(MockCS, sub):
    """Mocks fetch_latest_acquisition chain (filter → select_related → order_by → first)."""
    (
        MockCS.objects.filter.return_value
        .select_related.return_value
        .order_by.return_value
        .first.return_value
    ) = sub
    MockCS.Status.ACTIVE = 'active'
    MockCS.Status.CANCELLED = 'cancelled'


# ── Successful login ─────────────────────────────────────────────────────────

class TestClientLoginSuccess(TestCase):

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_valid_credentials_returns_user(self, mock_get_user, MockCS):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(username='jsmith', password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        _stub_latest_acquisition(MockCS, _active_subscription())

        repo = DjangoAuthRepository()
        result = repo.authenticate('jsmith', 'correctpassword')

        self.assertIsNotNone(result)
        self.assertEqual(result.user.username, 'jsmith')
        user.check_password.assert_called_once_with('correctpassword')
        user.save.assert_not_called()

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_login_with_no_role_succeeds_if_other_checks_pass(self, mock_get_user, MockCS):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True, has_role=False)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        _stub_latest_acquisition(MockCS, _active_subscription())

        repo = DjangoAuthRepository()
        result = repo.authenticate('jsmith', 'pass1234')

        self.assertIsNotNone(result)


# ── Invalid credentials (wrong password) ─────────────────────────────────────

class TestClientLoginInvalidCredentials(TestCase):

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_wrong_password_raises_auth_001(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=False)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'wrongpassword')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)
        self.assertEqual(ctx.exception.http_status, 401)

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_wrong_password_error_message(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=False)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'wrong')

        expected = ERROR_REGISTRY[AppErrorCode.AUTH_INVALID_CREDENTIALS]
        self.assertEqual(ctx.exception.message, expected['message'])

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_wrong_password_does_not_update_last_login(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=False)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException):
            repo.authenticate('jsmith', 'wrong')

        user.save.assert_not_called()


class TestTouchLastLogin(TestCase):

    def test_completed_sign_in_updates_last_login(self):
        from client.features.security.lifecycle.auth.infrastructure.repositories import touch_last_login

        user = _user_orm()
        touch_last_login(user)

        self.assertIsNotNone(user.last_login)
        user.save.assert_called_once_with(update_fields=['last_login'])


# ── Non-existent user ────────────────────────────────────────────────────────

class TestClientLoginUserNotFound(TestCase):

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_nonexistent_user_raises_auth_001(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        UserModel = MagicMock()
        from django.contrib.auth import get_user_model as _real_get
        UserModel.DoesNotExist = Exception
        UserModel.objects.select_related.return_value.get.side_effect = UserModel.DoesNotExist('User not found')
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('nonexistent', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)
        self.assertEqual(ctx.exception.http_status, 401)

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_nonexistent_user_uses_same_error_as_wrong_password(self, mock_get_user):
        """Security: user enumeration is prevented by using the same
        error code for both non-existent user and wrong password."""
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        UserModel = MagicMock()
        UserModel.DoesNotExist = Exception
        UserModel.objects.select_related.return_value.get.side_effect = UserModel.DoesNotExist()
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('ghost_user', 'pass1234')

        # Same AUTH_001 code as wrong password — no user enumeration leak
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)


# ── Inactive user (is_active=False) ──────────────────────────────────────────

class TestClientLoginInactiveUser(TestCase):

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_inactive_user_raises_auth_003(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(is_active=False, password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('inactive_user', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ACCOUNT_INACTIVE)
        self.assertEqual(ctx.exception.http_status, 403)


class TestClientLoginClosedCompany(TestCase):

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_closed_company_raises_auth_019_even_if_user_inactive(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(is_active=False, password_valid=True)
        user.company.lifecycle = 'CLOSED'
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('closed_user', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_COMPANY_CLOSED)
        self.assertEqual(ctx.exception.http_status, 403)


class TestClientLoginInactiveUserDetails(TestCase):

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_inactive_user_error_detail(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(is_active=False, password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('inactive_user', 'pass1234')

        expected = ERROR_REGISTRY[AppErrorCode.AUTH_ACCOUNT_INACTIVE]
        self.assertEqual(ctx.exception.message, expected['message'])

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_inactive_user_password_is_checked_first(self, mock_get_user):
        """Even with valid password, inactive user is rejected AFTER
        password check (the code checks password first, then is_active)."""
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(is_active=False, password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('inactive_user', 'pass1234')

        user.check_password.assert_called_once()
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ACCOUNT_INACTIVE)


# ── Disabled role ────────────────────────────────────────────────────────────

class TestClientLoginDisabledRole(TestCase):

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_disabled_role_raises_auth_002(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True, role_active=False, role_name='Bloqueado')
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ROLE_DISABLED)
        self.assertEqual(ctx.exception.http_status, 403)

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_disabled_role_includes_role_name_in_context(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True, role_active=False, role_name='Auditor')
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.context.get('role'), 'Auditor')


# ── Suspended company (no active subscription) ──────────────────────────────

class TestClientLoginSuspendedCompany(TestCase):

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_no_subscription_raises_auth_006(self, mock_get_user, MockCS):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        # No subscription at all
        _stub_latest_acquisition(MockCS, None)

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_COMPANY_SUSPENDED)
        self.assertEqual(ctx.exception.http_status, 403)

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_suspended_admin_allowed_in_recovery_mode(self, mock_get_user, MockCS):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True, role_name='Administrator')
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        sub = MagicMock()
        sub.status = 'suspended'
        _stub_latest_acquisition(MockCS, sub)

        repo = DjangoAuthRepository()
        result = repo.authenticate('jsmith', 'pass1234')

        self.assertIs(result.user, user)
        self.assertEqual(result.access.mode, 'billing_recovery')

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_cancelled_subscription_raises_auth_006(self, mock_get_user, MockCS):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        _stub_latest_acquisition(MockCS, _inactive_subscription())

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_COMPANY_SUSPENDED)

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_cancelled_subscription_within_period_allows_login(self, mock_get_user, MockCS):
        """Cancelar conserva el acceso hasta end_date. No es suspensión de empresa."""
        from datetime import timedelta

        from django.utils import timezone

        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        period_end = timezone.now() + timedelta(days=4)
        sub = _inactive_subscription()
        sub.end_date = period_end
        plan = MagicMock()
        plan.is_active = True
        sub.subscription = plan
        _stub_latest_acquisition(MockCS, sub)

        result = DjangoAuthRepository().authenticate('jsmith', 'pass1234')

        self.assertIs(result.user, user)
        self.assertEqual(result.access.mode, 'full')

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_cancelled_subscription_after_end_date_raises_auth_006(self, mock_get_user, MockCS):
        from datetime import timedelta

        from django.utils import timezone

        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        sub = _inactive_subscription()
        sub.end_date = timezone.now() - timedelta(days=1)
        _stub_latest_acquisition(MockCS, sub)

        with self.assertRaises(AuthException) as ctx:
            DjangoAuthRepository().authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_COMPANY_SUSPENDED)

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_inactive_plan_raises_sub_001(self, mock_get_user, MockCS):
        """Adquisición ACTIVE pero plan de catálogo desactivado → denegar en login."""
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository
        from core.errors import SubscriptionException

        user = _user_orm(password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        _stub_latest_acquisition(MockCS, _active_subscription(plan_active=False))

        repo = DjangoAuthRepository()

        with self.assertRaises(SubscriptionException) as ctx:
            repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_NO_ACTIVE)
        self.assertEqual(ctx.exception.http_status, 403)

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_suspended_company_error_detail(self, mock_get_user, MockCS):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        _stub_latest_acquisition(MockCS, None)

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'pass1234')

        expected = ERROR_REGISTRY[AppErrorCode.AUTH_COMPANY_SUSPENDED]
        self.assertEqual(ctx.exception.message, expected['message'])


# ── Validation order: checks happen in correct sequence ──────────────────────

class TestClientLoginValidationOrder(TestCase):
    """Verifies that the authentication checks happen in the correct order:
    1. User exists → AUTH_001
    2. Password valid → AUTH_001
    3. User active → AUTH_003
    4. Role active → AUTH_002
    5. Company subscription active → AUTH_006
    """

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_nonexistent_user_checked_before_password(self, mock_get_user):
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        UserModel = MagicMock()
        UserModel.DoesNotExist = Exception
        UserModel.objects.select_related.return_value.get.side_effect = UserModel.DoesNotExist()
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('ghost', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_password_checked_before_is_active(self, mock_get_user):
        """Wrong password should fail with AUTH_001 even if user is inactive."""
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(is_active=False, password_valid=False)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'wrong')

        # Password check happens before is_active check
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_is_active_checked_before_role(self, mock_get_user):
        """Inactive user should fail with AUTH_003 even if role is also disabled."""
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(is_active=False, password_valid=True, role_active=False)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ACCOUNT_INACTIVE)

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('client.features.security.lifecycle.auth.infrastructure.repositories.get_user_model')
    def test_role_checked_before_subscription(self, mock_get_user, MockCS):
        """Disabled role should fail with AUTH_002 even if subscription is also suspended."""
        from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoAuthRepository

        user = _user_orm(password_valid=True, role_active=False)
        UserModel = MagicMock()
        UserModel.objects.select_related.return_value.get.return_value = user
        mock_get_user.return_value = UserModel

        repo = DjangoAuthRepository()

        with self.assertRaises(AuthException) as ctx:
            repo.authenticate('jsmith', 'pass1234')

        # Role check happens before subscription check
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ROLE_DISABLED)
        # CompanySubscription should never be queried
        MockCS.objects.filter.assert_not_called()


# ── Error codes HTTP status validation ───────────────────────────────────────

class TestLoginErrorCodesHTTPStatus(TestCase):
    """Ensures all auth error codes map to the correct HTTP status."""

    def test_auth_001_is_401(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_INVALID_CREDENTIALS]
        self.assertEqual(entry['http_status'], 401)

    def test_auth_002_is_403(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_ROLE_DISABLED]
        self.assertEqual(entry['http_status'], 403)

    def test_auth_003_is_403(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_ACCOUNT_INACTIVE]
        self.assertEqual(entry['http_status'], 403)

    def test_auth_006_is_403(self):
        entry = ERROR_REGISTRY[AppErrorCode.AUTH_COMPANY_SUSPENDED]
        self.assertEqual(entry['http_status'], 403)

    def test_auth_exception_inherits_correct_status(self):
        exc = AuthException(AppErrorCode.AUTH_INVALID_CREDENTIALS)
        self.assertEqual(exc.http_status, 401)

    def test_auth_exception_inactive_inherits_correct_status(self):
        exc = AuthException(AppErrorCode.AUTH_ACCOUNT_INACTIVE)
        self.assertEqual(exc.http_status, 403)

    def test_auth_exception_suspended_inherits_correct_status(self):
        exc = AuthException(AppErrorCode.AUTH_COMPANY_SUSPENDED)
        self.assertEqual(exc.http_status, 403)
