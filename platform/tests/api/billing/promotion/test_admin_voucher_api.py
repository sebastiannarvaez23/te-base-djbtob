"""I — Admin promotion voucher API tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from platform.features.billing.commerce.promotion.domain.schemas import BulkCreateResultSchema, VoucherSchema
from platform.features.billing.commerce.promotion.presentation.api import (
    PromotionRedemptionListView,
    PromotionVoucherBulkCreateView,
    PromotionVoucherDetailView,
    PromotionVoucherListCreateView,
    PromotionVoucherRevokeView,
)
from platform.tests.unit.billing.promotion.conftest import make_voucher_schema

pytestmark = pytest.mark.api

_MOD = 'platform.features.billing.commerce.promotion.presentation.api'


class AdminVoucherApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = MagicMock(pk=uuid.uuid4(), is_authenticated=True, id=uuid.uuid4())

    def _auth(self, request):
        force_authenticate(request, user=self.admin)
        return request

    def test_i1_list_requires_auth(self):
        req = self.factory.get('/api/v1/platform/promotions/vouchers/')
        resp = PromotionVoucherListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 401)

    def test_i2_list_admin_ok(self):
        from core.query import PaginatedResult
        voucher = make_voucher_schema()
        req = self._auth(self.factory.get('/api/v1/platform/promotions/vouchers/'))
        with patch(f'{_MOD}.ListVouchersUseCase') as UC:
            UC.return_value.execute.return_value = PaginatedResult(
                items=[voucher], total=1, page=0, page_size=20, total_pages=1,
            )
            resp = PromotionVoucherListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status_code'], 200)
        self.assertEqual(len(resp.data['data']['items']), 1)
        self.assertEqual(resp.data['data']['total'], 1)

    def test_i6_create_valid_returns_201(self):
        created = make_voucher_schema()
        now = datetime(2026, 7, 1, 12, 0, 0)
        req = self._auth(self.factory.post(
            '/api/v1/platform/promotions/vouchers/',
            {
                'voucher_type': 'GIFT',
                'scope': 'OPEN',
                'subscription_ids': [str(uuid.uuid4())],
                'benefit_months': 3,
                'redeem_valid_from': now.isoformat(),
                'redeem_valid_until': (now + timedelta(days=30)).isoformat(),
            },
            format='json',
        ))
        with patch(f'{_MOD}.CreateVoucherUseCase') as UC:
            UC.return_value.execute.return_value = created
            resp = PromotionVoucherListCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 201)
        self.assertIn('data', resp.data)

    def test_i7_bulk_create(self):
        result = BulkCreateResultSchema(created=2, failed=[], vouchers=[make_voucher_schema()])
        now = datetime(2026, 7, 1, 12, 0, 0)
        req = self._auth(self.factory.post(
            '/api/v1/platform/promotions/vouchers/bulk/',
            {
                'voucher_type': 'GIFT',
                'company_ids': [str(uuid.uuid4())],
                'subscription_ids': [str(uuid.uuid4())],
                'benefit_months': 3,
                'redeem_valid_from': now.isoformat(),
                'redeem_valid_until': (now + timedelta(days=30)).isoformat(),
            },
            format='json',
        ))
        with patch(f'{_MOD}.CreateBulkVouchersUseCase') as UC:
            UC.return_value.execute.return_value = result
            resp = PromotionVoucherBulkCreateView.as_view()(req)
        self.assertEqual(resp.status_code, 201)

    def test_i8_revoke(self):
        revoked = make_voucher_schema(status='REVOKED')
        pk = uuid.uuid4()
        req = self._auth(self.factory.post(f'/api/v1/platform/promotions/vouchers/{pk}/revoke/'))
        with patch(f'{_MOD}.RevokeVoucherUseCase') as UC:
            UC.return_value.execute.return_value = revoked
            resp = PromotionVoucherRevokeView.as_view()(req, pk=pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['status'], 'REVOKED')

    def test_i10_wrap_response_envelope(self):
        req = self._auth(self.factory.get(f'/api/v1/platform/promotions/vouchers/{uuid.uuid4()}/'))
        with patch(f'{_MOD}.GetVoucherUseCase') as UC:
            UC.return_value.execute.return_value = make_voucher_schema()
            resp = PromotionVoucherDetailView.as_view()(req, pk=uuid.uuid4())
        self.assertIn('status_code', resp.data)
        self.assertIn('message', resp.data)
        self.assertIn('data', resp.data)
