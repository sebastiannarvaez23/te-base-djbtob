"""Expire vouchers job integration."""

from datetime import timedelta

import pytest
from django.utils import timezone

from platform.features.billing.commerce.promotion.application.use_cases import ExpireVouchersUseCase
from platform.features.billing.commerce.promotion.models import PromotionVoucher
from platform.tests.integration.billing.promotion.conftest import create_voucher, redeem_voucher

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_e1_expire_job_marks_past_due_active(promo_repo, plan_pro):
    past = {
        'redeem_valid_from': timezone.now() - timedelta(days=60),
        'redeem_valid_until': timezone.now() - timedelta(days=1),
    }
    voucher = create_voucher(
        promo_repo,
        voucher_type='GIFT',
        scope='OPEN',
        subscription_ids=[plan_pro.id],
        benefit_months=1,
        validity=past,
    )
    count = ExpireVouchersUseCase(promo_repo).execute(now=timezone.now())
    assert count >= 1
    voucher.refresh_from_db()
    assert voucher.status == PromotionVoucher.Status.EXPIRED


def test_e2_redeemed_unchanged_by_expire(promo_repo, plan_pro, company_a, validity):
    from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository

    DjangoSubscriptionRepository().activate_plan(company_a.id, plan_pro.id)
    voucher = create_voucher(
        promo_repo,
        voucher_type='GIFT',
        scope='OPEN',
        subscription_ids=[plan_pro.id],
        benefit_months=1,
        validity=validity,
    )
    redeem_voucher(
        serial=voucher.serial,
        subscription_id=plan_pro.id,
        company_id=company_a.id,
        context='SETTINGS',
        idempotency_key='expire-redeemed',
    )
    ExpireVouchersUseCase(promo_repo).execute(now=timezone.now())
    voucher.refresh_from_db()
    assert voucher.status == PromotionVoucher.Status.REDEEMED
