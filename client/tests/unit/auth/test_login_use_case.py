"""
Unit tests for LoginUserUseCase.

No database required — the repository is replaced by a Mock.
These tests verify the use case behavior in isolation.

Note: authenticate() raises AuthException on failure (does NOT return None).
      The use case now returns only the user (tokens are generated in the view).
"""
from unittest import TestCase
from unittest.mock import MagicMock

from core.errors import AppErrorCode, AuthException
from client.features.security.lifecycle.auth.domain.schemas import AuthenticatedClient
from core.access.billing_recovery import LoginAccessResult
from client.features.security.lifecycle.auth.application.use_cases import LoginUserUseCase


class TestLoginUserUseCase(TestCase):

    def setUp(self):
        self.mock_repo = MagicMock()
        self.use_case = LoginUserUseCase(self.mock_repo)

    # ------------------------------------------------------------------
    # Successful case
    # ------------------------------------------------------------------

    def test_returns_user_when_credentials_are_valid(self):
        user_mock = MagicMock()
        user_mock.username = 'jsmith'
        self.mock_repo.authenticate.return_value = AuthenticatedClient(
            user=user_mock,
            access=LoginAccessResult(mode='full'),
        )

        result = self.use_case.execute(username='jsmith', password='pass1234')

        self.assertIsNotNone(result)
        self.assertEqual(result.user.username, 'jsmith')

    def test_calls_authenticate_with_correct_username_and_password(self):
        self.mock_repo.authenticate.return_value = MagicMock()

        self.use_case.execute(username='jsmith', password='pass1234')

        self.mock_repo.authenticate.assert_called_once_with('jsmith', 'pass1234')

    # ------------------------------------------------------------------
    # Invalid credentials case
    # ------------------------------------------------------------------

    def test_raises_auth_exception_when_credentials_are_invalid(self):
        self.mock_repo.authenticate.side_effect = AuthException(
            AppErrorCode.AUTH_INVALID_CREDENTIALS
        )

        with self.assertRaises(AuthException):
            self.use_case.execute(username='unknown', password='wrong')

    def test_raises_auth_exception_when_account_is_inactive(self):
        self.mock_repo.authenticate.side_effect = AuthException(
            AppErrorCode.AUTH_ACCOUNT_INACTIVE
        )

        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute(username='inactive_user', password='pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ACCOUNT_INACTIVE)

    def test_raises_auth_exception_when_role_is_disabled(self):
        self.mock_repo.authenticate.side_effect = AuthException(
            AppErrorCode.AUTH_ROLE_DISABLED
        )

        with self.assertRaises(AuthException) as ctx:
            self.use_case.execute(username='jsmith', password='pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ROLE_DISABLED)
