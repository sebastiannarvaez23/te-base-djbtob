"""J4–J6 — Onboarding promotion API tests."""

import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest
from rest_framework.test import APIRequestFactory

from core.errors import AppErrorCode, OnboardingException
from platform.features.billing.commerce.promotion.presentation.onboarding_api import (
    OnboardingPromotionApplyView,
    OnboardingPromotionValidateView,
)
from platform.tests.unit.billing.promotion.conftest import make_preview

pytestmark = pytest.mark.api

_MOD_VALIDATE = 'platform.features.billing.commerce.promotion.presentation.onboarding_api'
_MOD_APPLY = _MOD_VALIDATE


class OnboardingPromoApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.reg_id = uuid.uuid4()

    @patch(f'{_MOD_VALIDATE}._resolve_registration_id')
    def test_j4_validate_without_cookie_401(self, resolve):
        resolve.side_effect = OnboardingException(AppErrorCode.ONBOARDING_INVALID_TOKEN)
        req = self.factory.post('/api/v1/onboarding/promotions/validate/', {
            'serial': 'WLGX-GFT-X',
            'subscription_id': str(uuid.uuid4()),
        }, format='json')
        resp = OnboardingPromotionValidateView.as_view()(req)
        self.assertEqual(resp.status_code, 401)

    @patch(f'{_MOD_VALIDATE}.composition.build_validate_onboarding_use_case')
    @patch(f'{_MOD_VALIDATE}._resolve_registration_id')
    def test_j5_apply_with_state(self, resolve, _build_validate):
        resolve.return_value = self.reg_id
        state = MagicMock()
        state.model_dump.return_value = {'requires_payment': True}
        with patch(f'{_MOD_APPLY}.composition.build_apply_onboarding_use_case') as build_apply:
            build_apply.return_value.execute.return_value = state
            req = self.factory.post('/api/v1/onboarding/promotions/apply/', {
                'serial': 'WLGX-GFT-X',
                'subscription_id': str(uuid.uuid4()),
            }, format='json')
            resp = OnboardingPromotionApplyView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
