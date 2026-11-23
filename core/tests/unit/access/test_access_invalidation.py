"""Unit tests for access invalidation helpers and role gate."""

from __future__ import annotations

import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


class TestInvalidationHelpers(TestCase):

    @patch('core.access.subscription.SubscriptionCache.invalidate_by_functionality')
    def test_on_functionality_change(self, mock_inv):
        from core.access.invalidation import invalidate_on_functionality_change
        fid = uuid.uuid4()
        invalidate_on_functionality_change(fid)
        mock_inv.assert_called_once_with(fid)

    @patch('core.access.subscription.SubscriptionCache.invalidate_by_module')
    def test_on_module_change(self, mock_inv):
        from core.access.invalidation import invalidate_on_module_change
        mid = uuid.uuid4()
        invalidate_on_module_change(mid)
        mock_inv.assert_called_once_with(mid)

    @patch('core.access.subscription.SubscriptionCache.bump_catalog_epoch')
    @patch('core.access.subscription.SubscriptionCache.invalidate_subscription')
    def test_on_plan_change(self, mock_inv, mock_bump):
        from core.access.invalidation import invalidate_on_subscription_plan_change
        sid = uuid.uuid4()
        invalidate_on_subscription_plan_change(sid)
        mock_inv.assert_called_once_with(str(sid))
        mock_bump.assert_called_once()

    @patch('core.access.subscription.SubscriptionCache.bump_catalog_epoch')
    def test_on_section_change(self, mock_bump):
        from core.access.invalidation import invalidate_on_section_change
        invalidate_on_section_change(uuid.uuid4())
        mock_bump.assert_called_once()


class TestHasSubscriptionAccessRoleGate(TestCase):

    def test_role_without_feature_raises_perm_002(self):
        from core.permissions import HasSubscriptionAccess
        from core.errors.codes import AppErrorCode
        from core.errors.exceptions import PermissionException

        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, rol_id='r1', pk='u1')
        request.user.rol = MagicMock(id='r1', is_active=True)

        with patch(
            'core.access.role_cache.RoleFeatureCache.get_or_load',
            return_value={'orders.view'},
        ):
            with self.assertRaises(PermissionException) as ctx:
                HasSubscriptionAccess._assert_role_allows(request, 'orders.create')
        self.assertEqual(ctx.exception.code, AppErrorCode.PERM_FEATURE_NOT_ALLOWED)

    def test_inactive_role_raises_auth_002(self):
        from core.permissions import HasSubscriptionAccess
        from core.errors.codes import AppErrorCode
        from core.errors.exceptions import AuthException

        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, rol_id='r1', pk='u1')
        request.user.rol = MagicMock(id='r1', is_active=False)

        with self.assertRaises(AuthException) as ctx:
            HasSubscriptionAccess._assert_role_allows(request, 'orders.create')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ROLE_DISABLED)

    @patch(
        'platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access',
        return_value=({'connectors.sap'}, {'connectors'}),
    )
    def test_company_admin_uses_licensed_complement_without_role_key(self, _complements):
        from core.permissions import HasSubscriptionAccess

        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, rol_id='r1', pk='u1', company_id='c1')
        request.user.rol = MagicMock(id='r1', is_active=True)
        request.user.rol.name = 'Administrator'

        with patch(
            'core.access.role_cache.RoleFeatureCache.get_or_load',
            return_value={'orders.view'},
        ):
            HasSubscriptionAccess._assert_role_allows(request, 'connectors.sap')

    @patch(
        'platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access',
        return_value=({'connectors.sap'}, {'connectors'}),
    )
    def test_other_role_does_not_inherit_company_complement(self, _complements):
        from core.permissions import HasSubscriptionAccess
        from core.errors.codes import AppErrorCode
        from core.errors.exceptions import PermissionException

        request = MagicMock()
        request.user = MagicMock(is_authenticated=True, rol_id='r1', pk='u1', company_id='c1')
        request.user.rol = MagicMock(id='r1', is_active=True)
        request.user.rol.name = 'Operator'

        with patch(
            'core.access.role_cache.RoleFeatureCache.get_or_load',
            return_value={'orders.view'},
        ):
            with self.assertRaises(PermissionException) as ctx:
                HasSubscriptionAccess._assert_role_allows(request, 'connectors.sap')
        self.assertEqual(ctx.exception.code, AppErrorCode.PERM_FEATURE_NOT_ALLOWED)
