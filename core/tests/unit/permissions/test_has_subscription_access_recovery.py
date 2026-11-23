"""HasSubscriptionAccess behaviour in billing recovery mode."""
import uuid
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors import AppErrorCode
from core.errors.exceptions import SubscriptionException
from core.permissions import HasSubscriptionAccess


class TestHasSubscriptionAccessRecovery(TestCase):

    def setUp(self):
        self.permission = HasSubscriptionAccess()
        self.view = SimpleNamespace(subscription_functionality='orders.create')
        self.company = MagicMock(id=uuid.uuid4())

    def _request(self, *, feature='orders.create', access_mode='billing_recovery'):
        user = MagicMock()
        user.company_id = self.company.id
        user.company = self.company
        # Esta suite cubre el modo billing_recovery, no permisos por rol.
        user.rol_id = None
        user.rol = None
        return SimpleNamespace(
            user=user,
            auth={'access_mode': access_mode},
            method='GET',
        )

    def test_recovery_denies_non_allowlisted_feature(self):
        with self.assertRaises(SubscriptionException) as ctx:
            self.permission.has_permission(self._request(), self.view)

        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_RECOVERY_DENIED)

    def test_recovery_allows_billing_feature(self):
        view = SimpleNamespace(
            subscription_functionality='settings.payment-methods.view',
        )
        allowed = self.permission.has_permission(self._request(), view)
        self.assertTrue(allowed)

    @patch('core.permissions.AccessChecker')
    def test_full_mode_uses_access_checker(self, MockChecker):
        MockChecker.check_feature.return_value = MagicMock(is_allowed=True)
        view = SimpleNamespace(subscription_functionality='orders.create')
        request = self._request(access_mode='full')

        allowed = self.permission.has_permission(request, view)

        self.assertTrue(allowed)
        MockChecker.check_feature.assert_called_once()
