"""Onboarding promotion step unit tests."""

import uuid
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

from core.errors import AppErrorCode, AppException, OnboardingException
from platform.features.billing.commerce.promotion.application.onboarding import (
    ApplyOnboardingPromotionUseCase,
    ValidateOnboardingPromotionUseCase,
)
from platform.tests.unit.billing.promotion.conftest import make_preview

pytestmark = pytest.mark.unit

_MOD = 'platform.features.billing.commerce.promotion.application.onboarding'


class TestOnboardingPromotionStep(TestCase):

    def setUp(self):
        self.reg_id = uuid.uuid4()
        self.sub_id = uuid.uuid4()
        self.registration = MagicMock()
        self.validate = MagicMock()

    def _validate_uc(self):
        return ValidateOnboardingPromotionUseCase(
            registration=self.registration, validate_use_case=self.validate,
        )

    def _apply_uc(self):
        return ApplyOnboardingPromotionUseCase(
            registration=self.registration, validate_use_case=self.validate,
        )

    @patch(f'{_MOD}.ensure_active')
    def test_validate_requires_subscription_selected(self, _ensure):
        reg = MagicMock(subscription_selected=False, subscription_id=None)
        self.registration.get.return_value = reg
        with self.assertRaises(OnboardingException) as ctx:
            self._validate_uc().execute(
                self.reg_id, serial='WLGX-GFT-X', subscription_id=self.sub_id,
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.ONBOARDING_STEP_OUT_OF_ORDER)

    @patch(f'{_MOD}.ensure_active')
    def test_validate_rejects_subscription_mismatch(self, _ensure):
        other_sub_id = uuid.uuid4()
        reg = MagicMock(subscription_selected=True, subscription_id=self.sub_id)
        self.registration.get.return_value = reg
        with self.assertRaises(AppException) as ctx:
            self._validate_uc().execute(
                self.reg_id, serial='WLGX-GFT-X', subscription_id=other_sub_id,
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INCOMPATIBLE)
        self.validate.execute.assert_not_called()

    @patch(f'{_MOD}.build_state_schema')
    @patch(f'{_MOD}.ensure_active')
    def test_apply_gift_skips_payment(self, _ensure, MockState):
        reg = MagicMock(
            subscription_selected=True,
            subscription_id=self.sub_id,
            subscription_data={'billing_interval': 'monthly'},
        )
        self.registration.get.return_value = reg
        self.validate.execute.return_value = make_preview(
            voucher_type='GIFT', final_amount=Decimal('0'),
        )
        MockState.return_value = MagicMock(requires_payment=False)
        state = self._apply_uc().execute(
            self.reg_id, serial='WLGX-GFT-X', subscription_id=self.sub_id,
        )
        self.registration.save_promotion_apply.assert_called_once()
        self.assertFalse(state.requires_payment)
        schema = self.validate.execute.call_args.args[0]
        self.assertEqual(schema.billing_interval, 'monthly')

    @patch(f'{_MOD}.build_state_schema')
    @patch(f'{_MOD}.ensure_active')
    def test_apply_discount_requires_payment(self, _ensure, MockState):
        reg = MagicMock(
            subscription_selected=True,
            subscription_id=self.sub_id,
            subscription_data={},
        )
        self.registration.get.return_value = reg
        self.validate.execute.return_value = make_preview(
            voucher_type='DISCOUNT',
            final_amount=Decimal('80'),
            discount_percent=Decimal('20'),
        )
        MockState.return_value = MagicMock(requires_payment=True)
        state = self._apply_uc().execute(
            self.reg_id, serial='WLGX-DSC-X', subscription_id=self.sub_id,
        )
        self.registration.save_promotion_apply.assert_called_once()
        self.assertTrue(state.requires_payment)

    @patch(f'{_MOD}.ensure_active')
    def test_apply_rejects_subscription_mismatch(self, _ensure):
        other_sub_id = uuid.uuid4()
        reg = MagicMock(subscription_selected=True, subscription_id=self.sub_id)
        self.registration.get.return_value = reg
        with self.assertRaises(AppException) as ctx:
            self._apply_uc().execute(
                self.reg_id, serial='WLGX-GFT-X', subscription_id=other_sub_id,
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.PROMO_INCOMPATIBLE)
        self.validate.execute.assert_not_called()
        self.registration.save_promotion_apply.assert_not_called()
