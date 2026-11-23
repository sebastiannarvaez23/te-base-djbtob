"""Renewal integration with discount benefits."""

import uuid
from decimal import Decimal

import pytest

from platform.features.billing.commerce.promotion import composition
from platform.features.billing.commerce.promotion.models import PromotionBenefit
from platform.features.billing.subscription.subscription.infrastructure.repositories import DjangoSubscriptionRepository
from platform.tests.integration.billing.promotion.conftest import create_voucher, redeem_voucher

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_g4_renewal_discount_reduced_amount(
    promo_repo, company_a, plan_pro, validity,
):
    DjangoSubscriptionRepository().activate_plan(company_a.id, plan_pro.id)
    voucher = create_voucher(
        promo_repo,
        voucher_type='DISCOUNT',
        scope='OPEN',
        subscription_ids=[plan_pro.id],
        discount_percent=Decimal('20'),
        discount_duration_months=3,
        validity=validity,
        serial=f'WLGX-DSC-RNW{uuid.uuid4().hex[:6].upper()}',
    )
    redeem_voucher(
        serial=voucher.serial,
        subscription_id=plan_pro.id,
        company_id=company_a.id,
        context='SETTINGS',
        idempotency_key=f'disc-renew-{uuid.uuid4().hex}',
    )
    amount, meta, skip = composition.get_renewal_charge_amount(company_a.id, plan_pro.price)
    assert skip is False
    assert amount == Decimal('80.00')
    assert meta.get('voucher_type') == 'DISCOUNT'

    benefit = PromotionBenefit.objects.get(company_id=company_a.id, status='ACTIVE')
    assert benefit.remaining_discount_cycles == 3
    composition.after_successful_renewal_charge(company_a.id)
    benefit.refresh_from_db()
    assert benefit.remaining_discount_cycles == 2
