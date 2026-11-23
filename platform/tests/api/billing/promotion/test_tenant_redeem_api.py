"""J — Tenant redeem/validate API tests."""

import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from platform.features.billing.commerce.promotion.presentation.api import (
    TenantRedeemVoucherView,
    TenantValidateVoucherView,
)
from platform.tests.unit.billing.promotion.conftest import make_preview, make_redeem_result

pytestmark = pytest.mark.api

_MOD = 'platform.features.billing.commerce.promotion.presentation.api'


class TenantRedeemApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = MagicMock(pk=uuid.uuid4(), is_authenticated=True)
        self.tenant_id = uuid.uuid4()

    def _tenant_request(self, method, path, data=None):
        if method == 'POST':
            req = self.factory.post(path, data or {}, format='json')
        else:
            req = self.factory.get(path)
        force_authenticate(req, user=self.user)
        req.tenant = MagicMock(id=self.tenant_id)
        return req

    @patch(f'{_MOD}.HasSubscriptionAccess.has_permission', return_value=True)
    def test_j1_validate_preview(self, _perm):
        preview = make_preview()
        req = self._tenant_request('POST', '/api/v1/promotions/validate/', {
            'serial': 'WLGX-GFT-TEST0001',
            'subscription_id': str(uuid.uuid4()),
        })
        with patch(f'{_MOD}.ValidateVoucherUseCase') as UC:
            UC.return_value.execute.return_value = preview
            resp = TenantValidateVoucherView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['final_amount'], str(preview.final_amount))

    @patch(f'{_MOD}.HasSubscriptionAccess.has_permission', return_value=True)
    def test_j2_redeem_success(self, _perm):
        result = make_redeem_result()
        req = self._tenant_request('POST', '/api/v1/promotions/redeem/', {
            'serial': 'WLGX-GFT-TEST0001',
            'subscription_id': str(uuid.uuid4()),
        })
        with patch(f'{_MOD}.RedeemVoucherUseCase') as UC:
            UC.return_value.execute.return_value = result
            resp = TenantRedeemVoucherView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('redemption', resp.data['data'])
