"""DB fixtures for promotion integration tests."""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from platform.features.billing.commerce.promotion.domain.schemas import CreateVoucherSchema
from platform.features.billing.commerce.promotion.infrastructure.repositories import (
    DjangoPromotionVoucherRepository,
)
from platform.features.billing.commerce.promotion.models import PromotionBenefit, PromotionVoucher
from platform.features.billing.subscription.subscription.infrastructure.repositories import (
    DjangoSubscriptionRepository,
)
from platform.features.billing.subscription.subscription.models import Subscription
from platform.features.company.tenant.company.models import Company, Domain


@pytest.fixture
def promo_repo():
    return DjangoPromotionVoucherRepository()


@pytest.fixture
def validity():
    now = timezone.now()
    return {
        'redeem_valid_from': now - timedelta(days=1),
        'redeem_valid_until': now + timedelta(days=30),
    }


@pytest.fixture
def plan_basic(db):
    return Subscription.objects.create(
        name='Basic',
        code=f'basic_{uuid.uuid4().hex[:6]}',
        price=Decimal('50.00'),
        is_active=True,
    )


@pytest.fixture
def plan_pro(db):
    return Subscription.objects.create(
        name='Pro',
        code=f'pro_{uuid.uuid4().hex[:6]}',
        price=Decimal('100.00'),
        is_active=True,
    )


@pytest.fixture
def plan_enterprise(db):
    return Subscription.objects.create(
        name='Enterprise',
        code=f'ent_{uuid.uuid4().hex[:6]}',
        price=Decimal('200.00'),
        is_active=True,
    )


@pytest.fixture
def cleanup_schemas():
    created: list[str] = []
    yield created
    with connection.cursor() as cursor:
        for schema in created:
            if schema != 'public':
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def _make_company(schema_suffix: str, name: str, cleanup_schemas: list) -> Company:
    from conftest import ensure_test_geo_city

    schema = f'prm_{schema_suffix}_{uuid.uuid4().hex[:6]}'
    cleanup_schemas.append(schema)
    company = Company.objects.create(
        schema_name=schema,
        name=name,
        nit=f'NIT{uuid.uuid4().hex[:8]}',
        address='Test',
        geo_city_id=ensure_test_geo_city(),
    )
    Domain.objects.create(
        domain=f'{schema}.test.local',
        tenant=company,
        is_primary=True,
    )
    return company


@pytest.fixture
def company_a(db, cleanup_schemas):
    return _make_company('a', 'Company A', cleanup_schemas)


@pytest.fixture
def company_b(db, cleanup_schemas):
    return _make_company('b', 'Company B', cleanup_schemas)


def create_voucher(
    repo: DjangoPromotionVoucherRepository,
    *,
    voucher_type: str = 'GIFT',
    scope: str = 'OPEN',
    subscription_ids: list,
    benefit_months: int = 3,
    discount_percent: Decimal | None = None,
    company_id=None,
    serial: str | None = None,
    validity: dict | None = None,
    discount_duration_months: int = 1,
) -> PromotionVoucher:
    v = validity or {
        'redeem_valid_from': timezone.now() - timedelta(days=1),
        'redeem_valid_until': timezone.now() + timedelta(days=30),
    }
    schema = CreateVoucherSchema(
        voucher_type=voucher_type,
        scope=scope,
        company_id=company_id,
        subscription_ids=subscription_ids,
        benefit_months=benefit_months if voucher_type == 'GIFT' else None,
        discount_percent=discount_percent,
        discount_duration_months=discount_duration_months,
        redeem_valid_from=v['redeem_valid_from'],
        redeem_valid_until=v['redeem_valid_until'],
    )
    if serial:
        result = repo.create(schema, serial=serial)
    else:
        result = repo.create(schema)
    return PromotionVoucher.objects.get(id=result.id)


def redeem_voucher(
    *,
    serial: str,
    subscription_id,
    company_id,
    context: str = 'SETTINGS',
    idempotency_key: str | None = None,
    payment_method_id=None,
):
    """Redeem via the composition-wired use case (replaces the old repo.redeem)."""
    from platform.features.billing.commerce.promotion.composition import build_redeem_use_case
    from platform.features.billing.commerce.promotion.domain.schemas import RedeemVoucherSchema

    return build_redeem_use_case().execute(RedeemVoucherSchema(
        serial=serial,
        subscription_id=subscription_id,
        company_id=company_id,
        context=context,
        idempotency_key=idempotency_key,
        payment_method_id=payment_method_id,
    ))


def validate_voucher(*, serial: str, subscription_id, company_id=None, context: str = 'SETTINGS'):
    """Validate/price via the composition-wired use case (replaces repo.validate_preview)."""
    from platform.features.billing.commerce.promotion.composition import build_validate_use_case
    from platform.features.billing.commerce.promotion.domain.schemas import ValidateVoucherSchema

    return build_validate_use_case().execute(ValidateVoucherSchema(
        serial=serial,
        subscription_id=subscription_id,
        company_id=company_id,
        context=context,
    ))


@pytest.fixture
def voucher_gift_pro_open(promo_repo, plan_pro, validity):
    return create_voucher(
        promo_repo,
        voucher_type='GIFT',
        scope='OPEN',
        subscription_ids=[plan_pro.id],
        benefit_months=3,
        validity=validity,
    )


@pytest.fixture
def voucher_discount_pro_20(promo_repo, plan_pro, validity):
    return create_voucher(
        promo_repo,
        voucher_type='DISCOUNT',
        scope='OPEN',
        subscription_ids=[plan_pro.id],
        discount_percent=Decimal('20'),
        discount_duration_months=1,
        validity=validity,
    )


@pytest.fixture
def voucher_gift_company_a(promo_repo, plan_pro, company_a, validity):
    return create_voucher(
        promo_repo,
        voucher_type='GIFT',
        scope='COMPANY',
        company_id=company_a.id,
        subscription_ids=[plan_pro.id],
        benefit_months=3,
        validity=validity,
    )


@pytest.fixture
def voucher_first_take(promo_repo, plan_basic, plan_pro, validity):
    return create_voucher(
        promo_repo,
        voucher_type='DISCOUNT',
        scope='FIRST_TAKE',
        subscription_ids=[plan_basic.id, plan_pro.id],
        discount_percent=Decimal('50'),
        validity=validity,
    )


@pytest.fixture
def active_benefit_gift(promo_repo, company_a, plan_pro, validity):
    voucher = create_voucher(
        promo_repo,
        voucher_type='GIFT',
        scope='COMPANY',
        company_id=company_a.id,
        subscription_ids=[plan_pro.id],
        benefit_months=2,
        validity=validity,
        serial=f'WLGX-GFT-BENEFIT{uuid.uuid4().hex[:4].upper()}',
    )
    DjangoSubscriptionRepository().activate_plan(company_a.id, plan_pro.id)
    redeem_voucher(
        serial=voucher.serial,
        subscription_id=plan_pro.id,
        company_id=company_a.id,
        context='SETTINGS',
        idempotency_key=f'test-benefit-{uuid.uuid4().hex}',
    )
    return PromotionBenefit.objects.filter(company_id=company_a.id, status='ACTIVE').first()
