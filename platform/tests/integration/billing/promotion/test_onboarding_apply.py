"""Onboarding promotion apply integration."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from core.errors import AppErrorCode, AppException
from client.features.security.lifecycle.onboarding.models import CompanyRegistration
from platform.features.billing.commerce.promotion.application.onboarding import (
    ApplyOnboardingPromotionUseCase,
    ValidateOnboardingPromotionUseCase,
)
from platform.tests.integration.billing.promotion.conftest import create_voucher

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def registration_with_subscription(db, plan_pro):
    return CompanyRegistration.objects.create(
        email='promo@onb.test',
        nit='900999888',
        schema_name=f'onb_{uuid.uuid4().hex[:8]}',
        status=CompanyRegistration.Status.IN_PROGRESS,
        current_step=CompanyRegistration.Step.SUBSCRIPTION,
        company_data={'name': 'Promo Co', 'nit': '900999888'},
        admin_user_data={'email': 'promo@onb.test'},
        subscription_data={'subscription_id': str(plan_pro.id), 'price': str(plan_pro.price)},
        subscription_selected=True,
        subscription_id=plan_pro.id,
        requires_payment=True,
        expires_at=timezone.now() + timedelta(days=7),
    )


def test_j5_onboarding_apply_sets_state(promo_repo, registration_with_subscription, plan_pro, validity):
    voucher = create_voucher(
        promo_repo,
        voucher_type='DISCOUNT',
        scope='OPEN',
        subscription_ids=[plan_pro.id],
        discount_percent=Decimal('20'),
        validity=validity,
    )
    preview = ValidateOnboardingPromotionUseCase().execute(
        registration_with_subscription.id,
        serial=voucher.serial,
        subscription_id=plan_pro.id,
    )
    assert preview.final_amount == Decimal('80.00')

    state = ApplyOnboardingPromotionUseCase().execute(
        registration_with_subscription.id,
        serial=voucher.serial,
        subscription_id=plan_pro.id,
    )
    registration_with_subscription.refresh_from_db()
    assert registration_with_subscription.requires_payment is True
    assert registration_with_subscription.subscription_data.get('applied_voucher_serial') == voucher.serial
    assert state.requires_payment is True


def test_onboarding_apply_rejects_subscription_mismatch(
    registration_with_subscription, plan_pro, validity, promo_repo,
):
    other_sub_id = uuid.uuid4()
    voucher = create_voucher(
        promo_repo,
        voucher_type='GIFT',
        scope='OPEN',
        subscription_ids=[plan_pro.id],
        validity=validity,
    )
    with pytest.raises(AppException) as exc:
        ApplyOnboardingPromotionUseCase().execute(
            registration_with_subscription.id,
            serial=voucher.serial,
            subscription_id=other_sub_id,
        )
    assert exc.value.code == AppErrorCode.PROMO_INCOMPATIBLE
