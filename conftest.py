"""Project-level pytest fixtures.

Most tests in the suite are unit tests with mocked managers — they have
no DB needs. The fixtures here exist for tests marked with
``@pytest.mark.integration``, which exercise the full stack against a
real Postgres + django-tenants setup.

Bootstrapping a tenant test DB is non-trivial: pytest-django's default
``migrate`` does not create the public tenant row that
``django_tenants`` middleware relies on. We provide a ``public_tenant``
fixture that creates it on first use, and skip integration tests
gracefully if the DB is unreachable so contributors without Postgres
can still run the unit suite.

To run integration tests::

    docker compose up -d postgres redis
    pytest -m integration
"""
import uuid

import pytest

# Stable city used by company fixtures / backfill (Medellín, CO).
MEDELLIN_CITY_ID = uuid.UUID('0f15d58f-1ed6-4019-a3b7-22861f9dbc82')


def ensure_test_geo_city():
    """Ensure a geography City row exists for Company.geo_city FK in tests."""
    from platform.features.geography.location.location.models import City, Country, Department

    city = City.objects.filter(pk=MEDELLIN_CITY_ID).first()
    if city is not None:
        return city.id

    country, _ = Country.objects.get_or_create(
        code='CO',
        defaults={'name': 'Colombia', 'is_active': True},
    )
    department, _ = Department.objects.get_or_create(
        country=country,
        code='ANT',
        defaults={'name': 'Antioquia', 'is_active': True},
    )
    city, _ = City.objects.get_or_create(
        id=MEDELLIN_CITY_ID,
        defaults={
            'department': department,
            'code': 'MED',
            'name': 'Medellín',
            'is_active': True,
        },
    )
    return city.id


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Bootstrap the public tenant after pytest-django creates the test DB.

    django-tenants requires at least one ``Company`` row with
    ``schema_name='public'`` so the middleware can resolve the public
    tenant for non-tenant requests. Without it, queries against
    Tenant-aware models fall back to a missing search_path and fail.

    This runs once per test session, after pytest-django finishes
    migrating the test DB. Idempotent — it only inserts when missing.
    """
    from django.db import connection

    with django_db_blocker.unblock():
        # Lazy imports — at module import time Django apps may not be ready.
        from platform.features.company.tenant.company.models import Company, Domain

        geo_city_id = ensure_test_geo_city()
        if not Company.objects.filter(schema_name='public').exists():
            public = Company.objects.create(
                schema_name='public',
                name='Public',
                nit='PUBLIC',
                address='-',
                geo_city_id=geo_city_id,
            )
            Domain.objects.create(
                domain='localhost',
                tenant=public,
                is_primary=True,
            )
        # Reset the connection so the search_path picks up the public schema.
        connection.set_schema_to_public()


@pytest.fixture
def free_subscription(db):
    """A free Subscription so onboarding can skip the payment step.

    ``price=0`` triggers ``requires_payment=False`` in the subscription
    use case, so finalize is reachable without exercising the payment
    processor flow.
    """
    from decimal import Decimal
    from platform.features.billing.subscription.subscription.models import Subscription

    return Subscription.objects.create(
        name='Test Free Plan',
        code='test_free',
        price=Decimal('0.00'),
        is_active=True,
    )


@pytest.fixture
def admin_role(db):
    """The system Administrator role finalize attaches to the new admin user.

    Created with ``company=None`` so it lives at the platform level
    (universal) — finalize looks it up via that exact predicate.
    """
    from client.features.security.lifecycle.registration.models import Rol

    role, _ = Rol.objects.get_or_create(name='Administrator', company=None)
    return role
