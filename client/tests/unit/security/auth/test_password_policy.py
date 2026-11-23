"""Unit tests for HISTORY_PASS / PASSWORD_EXPIRED policy."""
from datetime import timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from core.errors import AppErrorCode, AuthException

POLICY = 'client.features.security.lifecycle.auth.application.password_policy'
MODEL_PATH = 'client.features.security.lifecycle.auth.models.PasswordHistory'


def _user(*, password='old-secret', pk='user-pk'):
    user = MagicMock()
    user.pk = pk
    user.password = make_password(password) if password else ''
    user.password_changed_at = timezone.now()
    return user


class TestExpiryPolicy(TestCase):

    def setUp(self):
        from client.features.security.lifecycle.auth.application import password_policy as policy
        self.policy = policy

    def test_zero_days_never_expires(self):
        user = _user()
        user.password_changed_at = timezone.now() - timedelta(days=400)
        with patch(f'{POLICY}.get_parameter', return_value=0):
            self.assertFalse(self.policy.is_password_expired(user))

    def test_null_changed_at_is_grandfathered(self):
        user = _user()
        user.password_changed_at = None
        with patch(f'{POLICY}.get_parameter', return_value=90):
            self.assertFalse(self.policy.is_password_expired(user))

    def test_start_clock_stamps_null_when_policy_on(self):
        user = _user()
        user.password_changed_at = None
        with patch(f'{POLICY}.get_parameter', return_value=45):
            self.policy.start_password_clock(user)
        self.assertIsNotNone(user.password_changed_at)
        user.save.assert_called_with(update_fields=['password_changed_at'])
        self.assertFalse(self.policy.is_password_expired(user))

    def test_start_clock_noop_when_policy_off(self):
        user = _user()
        user.password_changed_at = None
        with patch(f'{POLICY}.get_parameter', return_value=0):
            self.policy.start_password_clock(user)
        self.assertIsNone(user.password_changed_at)

    def test_expired_when_older_than_window(self):
        user = _user()
        user.password_changed_at = timezone.now() - timedelta(days=91)
        with patch(f'{POLICY}.get_parameter', return_value=90):
            self.assertTrue(self.policy.is_password_expired(user))

    def test_not_expired_inside_window(self):
        user = _user()
        user.password_changed_at = timezone.now() - timedelta(days=10)
        with patch(f'{POLICY}.get_parameter', return_value=90):
            self.assertFalse(self.policy.is_password_expired(user))

    def test_bool_true_uses_default_window(self):
        user = _user()
        user.password_changed_at = timezone.now() - timedelta(days=91)
        with patch(f'{POLICY}.get_parameter', return_value=True):
            self.assertTrue(self.policy.is_password_expired(user))


class TestHistoryPolicy(TestCase):

    def setUp(self):
        from client.features.security.lifecycle.auth.application import password_policy as policy
        self.policy = policy

    def test_current_password_is_always_rejected(self):
        user = _user(password='KeepMe123')
        with patch(f'{POLICY}.get_parameter', return_value=0):
            with self.assertRaises(AuthException) as ctx:
                self.policy.rotate_password(user, 'KeepMe123')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_PASSWORD_REUSED)
        user.set_password.assert_not_called()

    def test_history_zero_allows_new_distinct_password(self):
        user = _user(password='KeepMe123')
        with patch(f'{POLICY}.get_parameter', return_value=0):
            self.policy.rotate_password(user, 'BrandNew456')
        user.set_password.assert_called_once_with('BrandNew456')
        user.save.assert_called_once_with(update_fields=['password', 'password_changed_at'])
        self.assertIsNotNone(user.password_changed_at)

    @patch(MODEL_PATH)
    def test_history_rejects_archived_password(self, model):
        user = _user(password='Current123')
        archived = make_password('Previous456')
        model.objects.filter.return_value.order_by.return_value.values_list.return_value = [archived]
        with patch(f'{POLICY}.get_parameter', return_value=5):
            with self.assertRaises(AuthException) as ctx:
                self.policy.rotate_password(user, 'Previous456')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_PASSWORD_REUSED)
        user.set_password.assert_not_called()

    @patch(MODEL_PATH)
    def test_rotate_archives_current_hash_and_trims(self, model):
        user = _user(password='Current123')
        old_hash = user.password
        qs = MagicMock()
        qs.order_by.return_value.values_list.return_value = []
        model.objects.filter.return_value = qs
        with patch(f'{POLICY}.get_parameter', return_value=5):
            self.policy.rotate_password(user, 'BrandNew456')
        model.objects.create.assert_called_once()
        self.assertEqual(model.objects.create.call_args.kwargs['password_hash'], old_hash)
        user.set_password.assert_called_once_with('BrandNew456')

    def test_bool_true_history_defaults_to_five(self):
        with patch(f'{POLICY}.get_parameter', return_value=True):
            self.assertEqual(self.policy.history_limit(), 5)
