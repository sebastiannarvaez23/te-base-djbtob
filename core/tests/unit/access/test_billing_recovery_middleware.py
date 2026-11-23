"""Unit tests for BillingRecoveryMiddleware."""
import json
import uuid
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from core.access.middleware import BillingRecoveryMiddleware


class TestBillingRecoveryMiddleware(TestCase):

    def _request(self, *, path='/api/v1/warehouse/orders/', access_mode='billing_recovery'):
        request = SimpleNamespace(path=path, access_mode=None, request_id='trace-123')
        return request

    @patch.object(BillingRecoveryMiddleware, '_resolve_access_mode', return_value='billing_recovery')
    def test_blocks_operational_api_in_recovery(self, _mock_mode):
        mw = BillingRecoveryMiddleware(lambda req: req)
        response = mw(self._request())

        self.assertEqual(response.status_code, 403)
        body = json.loads(response.content)
        self.assertEqual(body['error']['code'], 'SUB_006')
        self.assertEqual(body['error']['trace_id'], 'trace-123')

    @patch.object(BillingRecoveryMiddleware, '_resolve_access_mode', return_value='billing_recovery')
    def test_allows_auth_me_in_recovery(self, _mock_mode):
        seen = []
        mw = BillingRecoveryMiddleware(lambda req: seen.append(req) or req)
        request = self._request(path='/api/v1/auth/me/')

        response = mw(request)

        self.assertIs(response, request)
        self.assertEqual(seen, [request])

    @patch.object(BillingRecoveryMiddleware, '_resolve_access_mode', return_value='full')
    def test_full_mode_passes_through(self, _mock_mode):
        seen = []
        mw = BillingRecoveryMiddleware(lambda req: seen.append(req) or req)
        request = self._request()

        response = mw(request)

        self.assertIs(response, request)
