"""Redeem with subscription — matrix smoke (N)."""

import uuid
from decimal import Decimal

import pytest

from core.errors import AppErrorCode, ConflictException
from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository
from platform.tests.integration.billing.promotion.conftest import (
    create_voucher,
    redeem_voucher,
    validate_voucher,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_n_gift_open_settings_same_plan(promo_repo, company_a, plan_pro, validity):
    DjangoSubscriptionRepository().activate_plan(company_a.id, plan_pro.id)
    voucher = create_voucher(
        promo_repo, voucher_type='GIFT', scope='OPEN',
        subscription_ids=[plan_pro.id], benefit_months=2, validity=validity,
        serial=f'WLGX-GFT-N1{uuid.uuid4().hex[:5].upper()}',
    )
    result = redeem_voucher(
        serial=voucher.serial,
        subscription_id=plan_pro.id,
        company_id=company_a.id,
        context='SETTINGS',
        idempotency_key='n-gift-settings',
    )
    assert result.preview.final_amount == Decimal('0')


def test_n_discount_open_onboarding_preview(promo_repo, plan_pro, validity):
    voucher = create_voucher(
        promo_repo, voucher_type='DISCOUNT', scope='OPEN',
        subscription_ids=[plan_pro.id], discount_percent=Decimal('20'),
        validity=validity,
    )
    preview = validate_voucher(
        serial=voucher.serial,
        subscription_id=plan_pro.id,
        company_id=None,
        context='ONBOARDING',
    )
    assert preview.final_amount == Decimal('80.00')


def test_n_first_take_second_company_fails(
    promo_repo, company_a, company_b, plan_pro, validity,
):
    voucher = create_voucher(
        promo_repo, voucher_type='DISCOUNT', scope='FIRST_TAKE',
        subscription_ids=[plan_pro.id], discount_percent=Decimal('50'),
        validity=validity,
        serial=f'WLGX-DSC-FT{uuid.uuid4().hex[:5].upper()}',
    )
    DjangoSubscriptionRepository().activate_plan(company_a.id, plan_pro.id)
    DjangoSubscriptionRepository().activate_plan(company_b.id, plan_pro.id)
    redeem_voucher(
        serial=voucher.serial,
        subscription_id=plan_pro.id,
        company_id=company_a.id,
        context='SETTINGS',
        idempotency_key='first-take-a',
    )
    with pytest.raises(ConflictException) as exc:
        redeem_voucher(
            serial=voucher.serial,
            subscription_id=plan_pro.id,
            company_id=company_b.id,
            context='SETTINGS',
            idempotency_key='first-take-b',
        )
    assert exc.value.code == AppErrorCode.PROMO_ALREADY_CONSUMED
