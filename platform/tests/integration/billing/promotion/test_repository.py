"""Integration tests for DjangoPromotionVoucherRepository + redeem/validate use cases."""

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from core.errors import AppErrorCode, AppException, ConflictException, NotFoundException
from platform.features.billing.commerce.promotion.domain.schemas import (
    CreateBulkVouchersSchema,
    CreateVoucherSchema,
)
from platform.features.billing.commerce.promotion.models import PromotionVoucher
from platform.tests.integration.billing.promotion.conftest import (
    create_voucher,
    redeem_voucher,
    validate_voucher,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


class TestRepositoryCreate:

    def test_a1_1_gift_open_active_serial(self, promo_repo, plan_pro, validity):
        result = promo_repo.create(CreateVoucherSchema(
            voucher_type='GIFT',
            scope='OPEN',
            subscription_ids=[plan_pro.id],
            benefit_months=3,
            **validity,
        ))
        assert result.status == 'ACTIVE'
        assert result.serial.startswith('WLGX-GFT-')

    def test_a1_5_multiple_plans_m2m(self, promo_repo, plan_basic, plan_pro, plan_enterprise, validity):
        result = promo_repo.create(CreateVoucherSchema(
            voucher_type='GIFT',
            scope='OPEN',
            subscription_ids=[plan_basic.id, plan_pro.id, plan_enterprise.id],
            benefit_months=2,
            **validity,
        ))
        assert len(result.subscription_ids) == 3

    def test_a2_1_bulk_two_companies(self, promo_repo, plan_pro, company_a, company_b, validity):
        result = promo_repo.create_bulk(CreateBulkVouchersSchema(
            voucher_type='GIFT',
            company_ids=[company_a.id, company_b.id],
            subscription_ids=[plan_pro.id],
            benefit_months=3,
            **validity,
        ))
        assert result.created == 2
        serials = [v.serial for v in result.vouchers]
        assert len(set(serials)) == 2


class TestRepositoryValidateRedeem:

    def test_b1_3_case_insensitive_serial(self, promo_repo, voucher_gift_pro_open, plan_pro, company_a):
        preview = validate_voucher(
            serial=voucher_gift_pro_open.serial.lower(),
            subscription_id=plan_pro.id,
            company_id=company_a.id,
        )
        assert preview.final_amount == Decimal('0')

    def test_b1_2_serial_not_found(self, promo_repo, plan_pro, company_a):
        with pytest.raises(NotFoundException) as exc:
            validate_voucher(
                serial='WLGX-GFT-NOTFOUND',
                subscription_id=plan_pro.id,
                company_id=company_a.id,
            )
        assert exc.value.code == AppErrorCode.PROMO_NOT_FOUND

    def test_b1_10_wrong_company_scope(self, promo_repo, voucher_gift_company_a, plan_pro, company_b):
        with pytest.raises(AppException) as exc:
            validate_voucher(
                serial=voucher_gift_company_a.serial,
                subscription_id=plan_pro.id,
                company_id=company_b.id,
            )
        assert exc.value.code == AppErrorCode.PROMO_SCOPE_DENIED

    def test_c5_1_redeem_company_scope_ok(self, promo_repo, plan_pro, company_a, validity):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        DjangoSubscriptionRepository().activate_plan(company_a.id, plan_pro.id)
        v = create_voucher(
            promo_repo,
            voucher_type='GIFT',
            scope='COMPANY',
            company_id=company_a.id,
            subscription_ids=[plan_pro.id],
            benefit_months=1,
            validity=validity,
            serial=f'WLGX-GFT-{uuid.uuid4().hex[:8].upper()}',
        )
        result = redeem_voucher(
            serial=v.serial,
            subscription_id=plan_pro.id,
            company_id=company_a.id,
            context='SETTINGS',
            idempotency_key=f'redeem-{uuid.uuid4().hex}',
        )
        assert result.redemption.company_id == company_a.id
        assert PromotionVoucher.objects.get(serial=v.serial).status == 'REDEEMED'

    def test_f1_idempotent_redeem(self, promo_repo, voucher_gift_pro_open, plan_pro, company_a):
        from platform.features.billing.subscription.subscription.infrastructure.repositories import (
            DjangoSubscriptionRepository,
        )
        DjangoSubscriptionRepository().activate_plan(company_a.id, plan_pro.id)
        key = f'idem-{uuid.uuid4().hex}'
        common = dict(
            serial=voucher_gift_pro_open.serial,
            subscription_id=plan_pro.id,
            company_id=company_a.id,
            context='SETTINGS',
            idempotency_key=key,
        )
        r1 = redeem_voucher(**common)
        r2 = redeem_voucher(**common)
        assert r1.redemption.id == r2.redemption.id

    def test_b1_25_active_benefit_blocks(self, promo_repo, plan_pro, company_a, active_benefit_gift):
        v = promo_repo.create(CreateVoucherSchema(
            voucher_type='GIFT',
            scope='OPEN',
            subscription_ids=[plan_pro.id],
            benefit_months=1,
            redeem_valid_from=timezone.now() - timedelta(days=1),
            redeem_valid_until=timezone.now() + timedelta(days=30),
        ), serial=f'WLGX-GFT-{uuid.uuid4().hex[:8].upper()}')
        with pytest.raises(ConflictException) as exc:
            validate_voucher(
                serial=v.serial,
                subscription_id=plan_pro.id,
                company_id=company_a.id,
            )
        assert exc.value.code == AppErrorCode.PROMO_BENEFIT_ACTIVE
