"""End-to-end finalize integration test.

This is the only test in the suite that exercises the full onboarding
finalize against real Postgres + django-tenants. Every other onboarding
test mocks the ORM managers, so the most failure-prone moment — the
``auto_create_schema`` DDL that materialises the tenant's PostgreSQL
schema — is never proven by the unit suite.

What this test pins:

  * ``FinalizeOnboardingUseCase`` against a fully prepared
    registration creates a ``Company`` row, a ``Domain`` row, a
    ``CompanySubscription``, and an admin ``User``.
  * The PostgreSQL schema named ``schema_name`` actually exists in
    ``information_schema.schemata`` — i.e. ``auto_create_schema`` ran.
  * The ``CompanyRegistration`` row transitions to ``COMPLETED`` with
    ``finalized_company_id`` set.
  * The admin user lives in the *public* schema (User is shared across
    tenants in this project) but is bound to the new Company.

Marked ``@pytest.mark.integration`` and excluded from the default run
(see ``pytest.ini``); execute with::

    pytest -m integration

Schema cleanup runs in the fixture teardown so re-running the test
does not leave orphaned schemas in the test DB.
"""
import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from client.features.security.lifecycle.onboarding.infrastructure.finalize_composition import (
    compose_finalize_use_case,
)
from client.features.security.lifecycle.onboarding.infrastructure.repositories import (
    DjangoCompanyRegistrationRepository,
)
from client.features.security.lifecycle.onboarding.models import CompanyRegistration


class _FakePrivacyContent:
    policy_id = uuid.uuid4()
    country = 'CO'
    content_hash = 'a' * 64


@pytest.fixture
def cleanup_schema():
    """Track schemas created during the test and DROP them after.

    ``auto_create_schema=True`` runs ``CREATE SCHEMA`` outside the test
    transaction in some Postgres drivers — the savepoint rollback does
    not undo it. Explicit cleanup keeps the test DB tidy across runs.
    """
    created: list[str] = []

    yield created

    with connection.cursor() as cursor:
        for schema in created:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture
def prepared_registration(db, free_subscription):
    """A CompanyRegistration with all four data dicts populated, ready
    for finalize. Built directly on the model so this test is decoupled
    from the per-step submission use cases (those have their own unit
    coverage)."""
    schema = f'tst_{uuid.uuid4().hex[:8]}'
    from conftest import ensure_test_geo_city
    city_id = str(ensure_test_geo_city())

    return CompanyRegistration.objects.create(
        email='admin@acme-int.test',
        nit='900111222',
        schema_name=schema,
        status=CompanyRegistration.Status.IN_PROGRESS,
        current_step=CompanyRegistration.Step.CONFIRMATION,
        company_data={
            'name':    'Acme Integration',
            'nit':     '900111222',
            'address': '123 Test St',
            'country': 'Colombia',
            'country_code': 'CO',
            'state':   'Cundinamarca',
            'city':    'Bogota',
            'city_id': city_id,
        },
        admin_user_data={
            'email':         'admin@acme-int.test',
            'username':      'acme_admin',
            'first_name':    'Acme',
            'last_name':     'Admin',
            'telephone':     '3001234567',
            # Already-hashed; finalize assigns it directly to user.password.
            # (real flow hashes it during the admin-user step)
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


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_finalize_creates_tenant_and_admin_user(
    public_tenant_required,
    prepared_registration,
    admin_role,
    cleanup_schema,
    monkeypatch,
):
    """Happy path: finalize provisions the full tenant in one shot."""
    cleanup_schema.append(prepared_registration.schema_name)

    monkeypatch.setattr(
        'client.features.security.lifecycle.onboarding.application.use_cases.finalize.bind_privacy_country_to_company',
        lambda **kwargs: 'CO',
    )
    monkeypatch.setattr(
        'client.features.security.lifecycle.onboarding.application.use_cases.finalize.collect_onboarding_policies_to_seal',
        lambda **kwargs: [_FakePrivacyContent()],
    )
    monkeypatch.setattr(
        'client.features.security.lifecycle.onboarding.application.use_cases.finalize.sign_onboarding_policies',
        lambda **kwargs: None,
    )

    result = compose_finalize_use_case(
        DjangoCompanyRegistrationRepository(),
    ).execute(
        prepared_registration.id,
        privacy_accepted=True,
        privacy_content_hash='a' * 64,
        privacy_country='CO',
        terms_accepted=True,
        terms_content_hash='b' * 64,
    )

    # Result envelope
    assert result.company_id is not None
    assert result.email_confirmation_required is False  # default param

    # Registration transitioned
    prepared_registration.refresh_from_db()
    assert prepared_registration.status == CompanyRegistration.Status.COMPLETED
    assert prepared_registration.finalized_company_id == result.company_id

    # Tenant + Domain rows
    from platform.features.company.tenant.company.models import Company, Domain
    company = Company.objects.get(id=result.company_id)
    assert company.schema_name == prepared_registration.schema_name
    assert company.nit == '900111222'
    assert Domain.objects.filter(tenant=company).exists()

    # Subscription acquisition wired
    from platform.features.billing.subscription.subscription.models import CompanySubscription
    assert CompanySubscription.objects.filter(company=company).exists()

    # Admin user attached to the new company with the Administrator role
    from client.features.security.lifecycle.registration.models import User
    user = User.objects.get(username='acme_admin')
    assert user.company_id == company.id
    assert user.rol_id == admin_role.id

    # Postgres schema actually exists — this is what the unit suite cannot prove.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
            [prepared_registration.schema_name],
        )
        assert cursor.fetchone() is not None, (
            f'schema {prepared_registration.schema_name!r} was not created — '
            f'auto_create_schema regression?'
        )


@pytest.fixture
def public_tenant_required(db):
    """Skip the test cleanly when the test DB lacks the public tenant.

    The session-scoped ``django_db_setup`` fixture creates it normally,
    but if a contributor runs ``pytest -m integration`` against a DB
    that wasn't migrated with ``migrate_schemas``, the tables don't
    exist at all. Surface that as a skip with a helpful message rather
    than an opaque ``ProgrammingError``."""
    from django.db.utils import ProgrammingError

    try:
        from platform.features.company.tenant.company.models import Company
        if not Company.objects.filter(schema_name='public').exists():
            pytest.skip(
                'Public tenant missing. Run: '
                'python manage.py migrate_schemas --shared'
            )
    except ProgrammingError as exc:
        pytest.skip(f'Tenant tables not migrated: {exc}')
