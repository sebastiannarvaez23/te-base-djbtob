"""Gift upgrade and revert integration tests."""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from platform.features.billing.commerce.promotion import composition
from platform.features.billing.commerce.promotion.models import PromotionBenefit
from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository
from platform.features.billing.subscription.subscription.models import CompanySubscription
from platform.tests.integration.billing.promotion.conftest import create_voucher, redeem_voucher

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_c3_1_gift_upgrade_basic_to_enterprise(
    promo_repo, company_a, plan_basic, plan_enterprise, validity,
):
    DjangoSubscriptionRepository().activate_plan(company_a.id, plan_basic.id)
    voucher = create_voucher(
        promo_repo,
        voucher_type='GIFT',
        scope='OPEN',
        subscription_ids=[plan_enterprise.id],
        benefit_months=2,
        validity=validity,
        serial=f'WLGX-GFT-UPG{uuid.uuid4().hex[:6].upper()}',
    )
    redeem_voucher(
        serial=voucher.serial,
        subscription_id=plan_enterprise.id,
        company_id=company_a.id,
        context='SETTINGS',
        idempotency_key=f'upgrade-{uuid.uuid4().hex}',
    )
    active = CompanySubscription.objects.filter(
        company_id=company_a.id, status='ACTIVE',
    ).select_related('subscription').first()
    assert active.subscription_id == plan_enterprise.id

    benefit = PromotionBenefit.objects.get(company_id=company_a.id, status='ACTIVE')
    assert benefit.previous_subscription_id == plan_basic.id

    benefit.benefit_end = timezone.now() - timedelta(minutes=1)
    benefit.save(update_fields=['benefit_end'])
    assert composition.revert_expired_gift_benefits(now=timezone.now()) >= 1

    reverted = CompanySubscription.objects.filter(
        company_id=company_a.id, status='ACTIVE',
    ).select_related('subscription').first()
    assert reverted.subscription_id == plan_basic.id
