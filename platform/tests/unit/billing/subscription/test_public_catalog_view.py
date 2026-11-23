"""Unit tests for the public subscription catalog endpoint.

The view exposes ``GET /api/v1/subscriptions/`` to anonymous traffic
(onboarding wizard, marketing pages). The contract under test:

  * No authentication required (``authentication_classes = []``).
  * Delegates to ``GetActiveSubscriptionsUseCase`` — never touches
    ``GetAllSubscriptionsUseCase`` (would leak deactivated plans).
  * Response shape contains ONLY the public-facing fields. Operational
    metadata (``is_active``, timestamps) MUST be absent.
  * Wraps the response with ``wrap_response`` so the envelope is
    consistent with the rest of the API.

Driven via ``APIRequestFactory``; the use case is patched so the suite
runs without DB.
"""
import uuid
from decimal import Decimal
from unittest import mock
from unittest.mock import MagicMock

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from platform.features.billing.subscription.subscription.domain.schemas import SubscriptionSchema
from platform.features.billing.subscription.subscription.presentation.public_api import (
    PublicSubscriptionCatalogAPIView,
)


VIEW_PATH = 'platform.features.billing.subscription.subscription.presentation.public_api'

LOCMEM_CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'default-pubcat'},
    'access':  {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'access-pubcat'},
    'auth':    {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'auth-pubcat'},
}


def _plan(code='standard', price='49.99', name='Standard'):
    return SubscriptionSchema(
        id=uuid.uuid4(),
        name=name,
        price=Decimal(price),
        code=code,
        description=f'{name} description',
        logo='',
        is_active=True,
    )


def _get():
    factory = APIRequestFactory()
    request = factory.get('/api/v1/subscriptions/')
    return PublicSubscriptionCatalogAPIView.as_view()(request)


@override_settings(CACHES=LOCMEM_CACHES)
class _PublicCatalogTestBase(SimpleTestCase):

    def setUp(self):
        # Stub the repository factory so we don't construct the real one
        # (it would import the Subscription model on module load).
        repo_patch = mock.patch(f'{VIEW_PATH}.DjangoSubscriptionRepository', return_value=MagicMock())
        repo_patch.start()
        self.addCleanup(repo_patch.stop)

        uc_patch = mock.patch(f'{VIEW_PATH}.GetActiveSubscriptionsUseCase')
        self.use_case_cls = uc_patch.start()
        self.addCleanup(uc_patch.stop)
        self.use_case_instance = self.use_case_cls.return_value


class TestPublicCatalogResponseShape(_PublicCatalogTestBase):

    def test_returns_200_with_envelope_data_array(self):
        self.use_case_instance.execute.return_value = [
            _plan(code='basic', price='9.99', name='Basic'),
            _plan(code='pro', price='99.00', name='Pro'),
        ]

        response = _get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['data']), 2)

    def test_response_excludes_is_active(self):
        """``is_active`` is admin metadata. Leaking it on the public
        catalog would let anonymous traffic enumerate which plans the
        operator has deactivated."""
        self.use_case_instance.execute.return_value = [_plan()]

        response = _get()

        for plan in response.data['data']:
            self.assertNotIn('is_active', plan)

    def test_response_excludes_timestamps(self):
        """Internal audit fields don't belong on a marketing surface."""
        self.use_case_instance.execute.return_value = [_plan()]

        response = _get()

        for plan in response.data['data']:
            self.assertNotIn('created_at', plan)
            self.assertNotIn('updated_at', plan)

    def test_response_includes_yearly_price_with_annual_discount(self):
        self.use_case_instance.execute.return_value = [_plan(price='100.00')]

        response = _get()
        plan = response.data['data'][0]

        self.assertEqual(plan['price'], '100.00')
        self.assertEqual(plan['yearly_price'], '1020.00')
        self.assertEqual(plan['annual_discount_percent'], '15')

    def test_response_includes_public_fields_only(self):
        """The exact allowlist documented at the top of public_api.py.
        Adding a field here is a public-API change."""
        self.use_case_instance.execute.return_value = [_plan()]

        response = _get()
        plan = response.data['data'][0]

        self.assertEqual(
            set(plan.keys()),
            {'id', 'name', 'price', 'currency', 'yearly_price', 'annual_discount_percent',
             'code', 'description', 'logo'},
        )

    def test_empty_catalog_returns_empty_array(self):
        self.use_case_instance.execute.return_value = []

        response = _get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data'], [])


class TestPublicCatalogDelegation(_PublicCatalogTestBase):

    def test_uses_active_use_case_not_get_all(self):
        """Defence in depth: even if someone refactors the catalog
        view to also use ``GetAllSubscriptionsUseCase``, this test
        catches it."""
        self.use_case_instance.execute.return_value = []

        _get()

        self.use_case_cls.assert_called_once()
        self.use_case_instance.execute.assert_called_once_with()


class TestPublicCatalogAuthentication(SimpleTestCase):
    """Smoke test the access policy at the class level — these settings
    are the security boundary."""

    def test_no_authentication_classes_required(self):
        self.assertEqual(PublicSubscriptionCatalogAPIView.authentication_classes, [])

    def test_no_permission_classes_required(self):
        self.assertEqual(PublicSubscriptionCatalogAPIView.permission_classes, [])
