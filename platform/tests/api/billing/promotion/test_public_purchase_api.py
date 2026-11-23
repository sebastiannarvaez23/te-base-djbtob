"""M — Public purchase API tests."""

import uuid
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from platform.features.billing.commerce.promotion.presentation.public_api import (
    PublicPurchaseCheckoutView,
    PublicPurchasePreviewView,
)

pytestmark = pytest.mark.api

_MOD = 'platform.features.billing.commerce.promotion.presentation.public_api'


class PublicPurchaseApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()

    @patch(f'{_MOD}.composition.build_public_preview_use_case')
    def test_m1_preview_api(self, build_preview):
        preview_uc = build_preview.return_value
        preview_uc.execute.return_value = type('R', (), {
            'model_dump': lambda self, mode='json': {
                'amount': '299.00',
                'currency': 'USD',
                'description': 'Regalo Pro — 3 mes(es)',
            },
        })()
        req = self.factory.post('/api/v1/promotions/public/purchase/preview/', {
            'voucher_type': 'GIFT',
            'subscription_id': str(uuid.uuid4()),
            'benefit_months': 3,
        }, format='json')
        resp = PublicPurchasePreviewView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['amount'], '299.00')

    @patch(f'{_MOD}.composition.build_public_checkout_use_case')
    def test_m10_checkout_returns_serial(self, build_checkout):
        from datetime import datetime, timezone

        checkout_uc = build_checkout.return_value
        checkout_uc.execute.return_value = type('R', (), {
            'model_dump': lambda self, mode='json': {
                'voucher_serial': 'WLGX-GFT-PUBLIC01',
                'redeem_valid_until': datetime(2026, 12, 31, tzinfo=timezone.utc).isoformat(),
                'amount_paid': '299.00',
                'charge_id': str(uuid.uuid4()),
            },
        })()
        req = self.factory.post('/api/v1/promotions/public/purchase/checkout/', {
            'voucher_type': 'GIFT',
            'subscription_id': str(uuid.uuid4()),
            'benefit_months': 3,
            'buyer': {'name': 'Jane', 'email': 'jane@example.com'},
            'recipient': {'name': 'John', 'email': 'john@example.com'},
            'payment': {
                'processor_token': 'dev-token-abc',
                'holder': 'JANE',
                'last4': '4242',
                'expiry_month': 12,
                'expiry_year': 2030,
            },
            'idempotency_key': 'checkout-key-1',
        }, format='json')
        resp = PublicPurchaseCheckoutView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['voucher_serial'], 'WLGX-GFT-PUBLIC01')
