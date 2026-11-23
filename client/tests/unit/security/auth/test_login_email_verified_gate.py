"""Unit tests for the email-confirmation gate in DjangoAuthRepository.authenticate.

The gate guards login with the ``REG_EMAIL_CONFIRM`` runtime parameter:

  * gate OFF → an unverified user can still sign in (back-compat for
    tenants onboarded before the flag existed).
  * gate ON + ``email_verified_at IS NULL`` → AUTH_007 with the user id
    in ``context`` so the API layer can trigger the throttled resend.
  * gate ON + verified → login proceeds to the next check in the chain.

Invalid credentials must short-circuit *before* the gate check so the
HTTP response can't be used to enumerate which accounts exist but are
unconfirmed.

Tests patch ``get_user_model``, ``get_parameter``, and the lazily-imported
``CompanySubscription`` so no database is needed.
"""
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors import AppErrorCode, AuthException, EmailNotVerifiedException


REPO_PATH = 'client.features.security.lifecycle.auth.infrastructure.repositories'


def _user(*, verified: bool, is_active: bool = True):
    user = MagicMock()
    user.pk = 'user-pk-xyz'
    user.is_active = is_active
    user.email_verified_at = MagicMock() if verified else None
    user.check_password.return_value = True
    # Neutralize downstream checks that would run after the gate.
    user.rol = MagicMock(is_active=True)
    user.company = MagicMock(lifecycle='ACTIVE')
    return user


class _GateTestBase(TestCase):

    def setUp(self):
        self.User = MagicMock()
        user_patch = patch(f'{REPO_PATH}.get_user_model', return_value=self.User)
        user_patch.start()
        self.addCleanup(user_patch.stop)

        # CompanySubscription is resolved inside authenticate; provide a
        # module-level stub that always returns an ACTIVE subscription so
        # the default "happy after-gate" path is green.
        self._subscription_patch = patch.dict(
            'sys.modules',
            {'platform.features.billing.subscription.subscription.models': self._make_subscription_module()},
        )
        self._subscription_patch.start()
        self.addCleanup(self._subscription_patch.stop)

        from client.features.security.lifecycle.auth.infrastructure.repositories import (
            DjangoAuthRepository,
        )
        self.repo = DjangoAuthRepository()

    @staticmethod
    def _make_subscription_module():
        module = MagicMock()
        active_subscription = MagicMock()
        active_subscription.status = 'active'
        active_subscription.subscription.is_active = True
        module.CompanySubscription.Status.ACTIVE = 'active'
        (module.CompanySubscription.objects
         .filter.return_value
         .select_related.return_value
         .order_by.return_value
         .first.return_value) = active_subscription
        return module


class TestGateOff(_GateTestBase):

    def test_unverified_user_can_log_in_when_flag_is_false(self):
        """REG_EMAIL_CONFIRM=false preserves legacy behaviour — login must
        succeed for users whose email has never been confirmed."""
        self.User.objects.select_related.return_value.get.return_value = _user(verified=False)

        with patch(f'{REPO_PATH}.get_parameter', return_value=False):
            result = self.repo.authenticate('jsmith', 'pass1234')

        self.assertIsNotNone(result)

    def test_verified_user_can_log_in_when_flag_is_false(self):
        """Sanity: verified users aren't accidentally blocked when the gate is off."""
        self.User.objects.select_related.return_value.get.return_value = _user(verified=True)

        with patch(f'{REPO_PATH}.get_parameter', return_value=False):
            self.repo.authenticate('jsmith', 'pass1234')


class TestGateOn(_GateTestBase):

    def test_unverified_user_is_blocked_with_auth_007(self):
        self.User.objects.select_related.return_value.get.return_value = _user(verified=False)

        with patch(f'{REPO_PATH}.get_parameter', return_value=True):
            with self.assertRaises(EmailNotVerifiedException) as ctx:
                self.repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_EMAIL_NOT_VERIFIED)

    def test_blocked_exception_carries_user_id_for_resend(self):
        """The API layer uses ``context['user_id']`` to trigger the throttled
        resend — dropping it would break the auto-resend feature."""
        user = _user(verified=False)
        self.User.objects.select_related.return_value.get.return_value = user

        with patch(f'{REPO_PATH}.get_parameter', return_value=True):
            with self.assertRaises(EmailNotVerifiedException) as ctx:
                self.repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.context['user_id'], str(user.pk))

    def test_verified_user_bypasses_the_gate(self):
        self.User.objects.select_related.return_value.get.return_value = _user(verified=True)

        with patch(f'{REPO_PATH}.get_parameter', return_value=True):
            # Should not raise EmailNotVerifiedException; downstream checks pass.
            self.repo.authenticate('jsmith', 'pass1234')


class TestAntiEnumeration(_GateTestBase):
    """Invalid credentials must never leak whether the account exists-but-
    unverified. AUTH_001 must surface before AUTH_007 regardless of flag."""

    def test_unknown_username_raises_invalid_credentials_not_email_not_verified(self):
        self.User.DoesNotExist = Exception
        self.User.objects.select_related.return_value.get.side_effect = self.User.DoesNotExist()

        with patch(f'{REPO_PATH}.get_parameter', return_value=True):
            with self.assertRaises(AuthException) as ctx:
                self.repo.authenticate('unknown', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)
        self.assertNotIsInstance(ctx.exception, EmailNotVerifiedException)

    def test_wrong_password_raises_invalid_credentials_even_when_unverified(self):
        user = _user(verified=False)
        user.check_password.return_value = False
        self.User.objects.select_related.return_value.get.return_value = user

        with patch(f'{REPO_PATH}.get_parameter', return_value=True):
            with self.assertRaises(AuthException) as ctx:
                self.repo.authenticate('jsmith', 'wrong')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_INVALID_CREDENTIALS)

    def test_inactive_account_raises_account_inactive_before_gate(self):
        """AUTH_003 takes precedence over AUTH_007 — a deactivated account
        shouldn't trigger a resend email on every attempt."""
        self.User.objects.select_related.return_value.get.return_value = _user(
            verified=False, is_active=False,
        )

        with patch(f'{REPO_PATH}.get_parameter', return_value=True):
            with self.assertRaises(AuthException) as ctx:
                self.repo.authenticate('jsmith', 'pass1234')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ACCOUNT_INACTIVE)


class TestGateReadsRuntimeParameter(_GateTestBase):
    """Runtime toggle: flipping REG_EMAIL_CONFIRM in the Parameter table
    changes behaviour without a deploy — the gate must consult it on every
    call, not cache at import time."""

    def test_gate_consults_parameter_once_per_login(self):
        self.User.objects.select_related.return_value.get.return_value = _user(verified=False)

        with patch(f'{REPO_PATH}.get_parameter', return_value=True) as gp:
            with self.assertRaises(EmailNotVerifiedException):
                self.repo.authenticate('jsmith', 'pass1234')

        gp.assert_called_with('REG_EMAIL_CONFIRM', default=False)

    def test_toggle_live_switches_behavior(self):
        """First call gate=OFF → login OK. Second call gate=ON → AUTH_007.
        Demonstrates no stale state between calls."""
        self.User.objects.select_related.return_value.get.return_value = _user(verified=False)

        with patch(f'{REPO_PATH}.get_parameter', return_value=False):
            self.repo.authenticate('jsmith', 'pass1234')  # first: pass

        with patch(f'{REPO_PATH}.get_parameter', return_value=True):
            with self.assertRaises(EmailNotVerifiedException):
                self.repo.authenticate('jsmith', 'pass1234')
