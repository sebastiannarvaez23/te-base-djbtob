"""Unit tests for billing recovery access policy."""
import uuid
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.access.billing_recovery import (
    get_request_access_mode,
    is_billing_recovery_api_path,
    is_billing_recovery_feature,
    resolve_login_access,
    resolve_login_access_for_user,
)


def _user(role_name='Operador'):
    user = MagicMock()
    user.company = MagicMock()
    user.company.id = uuid.uuid4()
    role = MagicMock()
    role.name = role_name
    user.rol = role
    return user


def _acquisition(status='suspended'):
    cs = MagicMock()
    cs.status = status
    return cs


class TestResolveLoginAccess(TestCase):

    def test_active_subscription_full_access(self):
        result = resolve_login_access(_user(), _acquisition('active'))
        self.assertEqual(result.mode, 'full')

    def test_suspended_admin_gets_recovery(self):
        result = resolve_login_access(_user('Administrator'), _acquisition('suspended'))
        self.assertEqual(result.mode, 'billing_recovery')
        self.assertEqual(result.subscription_status, 'suspended')

    def test_suspended_operator_denied_at_gate(self):
        result = resolve_login_access(_user('Operador'), _acquisition('suspended'))
        self.assertEqual(result.mode, 'full')
        self.assertEqual(result.subscription_status, 'suspended')

    def test_cancelled_not_recovery(self):
        result = resolve_login_access(_user('Administrator'), _acquisition('cancelled'))
        self.assertEqual(result.mode, 'full')


class TestBillingRecoveryAllowlists(TestCase):

    def test_feature_allowlist(self):
        self.assertTrue(is_billing_recovery_feature('settings.payment-methods.view'))
        self.assertFalse(is_billing_recovery_feature('orders.create'))

    def test_api_path_allowlist(self):
        self.assertTrue(
            is_billing_recovery_api_path('/api/v1/billing/payment-methods/'),
        )
        self.assertTrue(
            is_billing_recovery_api_path('/api/v1/billing/subscriptions/retry-payment/'),
        )
        self.assertTrue(
            is_billing_recovery_api_path('/api/v1/auth/me/'),
        )
        self.assertFalse(
            is_billing_recovery_api_path('/api/v1/warehouse/orders/'),
        )


class TestResolveLoginAccessForUser(TestCase):

    @patch('core.access.billing_recovery.fetch_latest_acquisition')
    def test_resolves_from_latest_acquisition(self, mock_fetch):
        user = _user('Administrator')
        mock_fetch.return_value = _acquisition('suspended')

        result = resolve_login_access_for_user(user)

        self.assertEqual(result.mode, 'billing_recovery')
        mock_fetch.assert_called_once_with(user.company)


class TestGetRequestAccessMode(TestCase):

    def test_reads_from_request_auth(self):
        request = SimpleNamespace(auth={'access_mode': 'billing_recovery'})
        self.assertEqual(get_request_access_mode(request), 'billing_recovery')

    def test_reads_from_middleware_attribute(self):
        request = SimpleNamespace(auth=None, access_mode='billing_recovery')
        self.assertEqual(get_request_access_mode(request), 'billing_recovery')

    def test_defaults_to_full(self):
        request = SimpleNamespace()
        self.assertEqual(get_request_access_mode(request), 'full')
