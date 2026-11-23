"""L3 — Finalize without voucher leaves no redemption."""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from client.features.security.lifecycle.onboarding.infrastructure.finalize_composition import (
    compose_finalize_use_case,
)
from client.features.security.lifecycle.onboarding.infrastructure.repositories import (
    DjangoCompanyRegistrationRepository,
)
from client.features.security.lifecycle.onboarding.models import CompanyRegistration
from platform.features.billing.commerce.promotion.models import PromotionRedemption

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def cleanup_schema():
    from django.db import connection
    created: list[str] = []
    yield created
    with connection.cursor() as cursor:
        for schema in created:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture
def public_tenant_required(db):
    from django.db.utils import ProgrammingError
    try:
        from platform.features.company.tenant.company.models import Company
        if not Company.objects.filter(schema_name='public').exists():
            pytest.skip('Public tenant missing. Run migrate_schemas --shared')
    except ProgrammingError as exc:
        pytest.skip(f'Tenant tables not migrated: {exc}')


def test_l3_finalize_without_voucher_no_redemption(
    public_tenant_required, free_subscription, admin_role, cleanup_schema, db, monkeypatch,
):
    schema = f'fin_{uuid.uuid4().hex[:8]}'
    from conftest import ensure_test_geo_city
    city_id = str(ensure_test_geo_city())
    reg = CompanyRegistration.objects.create(
        email='nofin@promo.test',
        nit='900222333',
        schema_name=schema,
        status=CompanyRegistration.Status.IN_PROGRESS,
        current_step=CompanyRegistration.Step.CONFIRMATION,
        company_data={
            'name': 'No Promo Co', 'nit': '900222333', 'address': '1',
            'country': 'Colombia', 'country_code': 'CO', 'state': 'X', 'city': 'Y',
            'city_id': city_id,
        },
        admin_user_data={
            'email': 'nofin@promo.test', 'username': 'nofin_admin',
            'first_name': 'No', 'last_name': 'Promo',
            'telephone': '3000000000',
            'password_hash': 'pbkdf2_sha256$dummy$dummy$dummy=',
        },
        subscription_data={'subscription_id': str(free_subscription.id)},
        payment_data={},
        company_data_completed=True,
        admin_user_completed=True,
        subscription_selected=True,
        payment_completed=True,
        subscription_id=free_subscription.id,
        requires_payment=False,
        expires_at=timezone.now() + timedelta(days=7),
    )
    cleanup_schema.append(schema)

    monkeypatch.setattr(
        'client.features.security.lifecycle.onboarding.application.use_cases.finalize.bind_privacy_country_to_company',
        lambda **kwargs: 'CO',
    )
    monkeypatch.setattr(
        'client.features.security.lifecycle.onboarding.application.use_cases.finalize.collect_onboarding_policies_to_seal',
        lambda **kwargs: [type('P', (), {
            'policy_id': uuid.uuid4(),
            'country': 'CO',
            'content_hash': 'a' * 64,
        })()],
    )
    monkeypatch.setattr(
        'client.features.security.lifecycle.onboarding.application.use_cases.finalize.sign_onboarding_policies',
        lambda **kwargs: None,
    )

    result = compose_finalize_use_case(DjangoCompanyRegistrationRepository()).execute(
        reg.id,
        privacy_accepted=True,
        privacy_content_hash='a' * 64,
        privacy_country='CO',
        terms_accepted=True,
        terms_content_hash='b' * 64,
    )
    assert result.company_id is not None
    assert PromotionRedemption.objects.filter(company_id=result.company_id).count() == 0
