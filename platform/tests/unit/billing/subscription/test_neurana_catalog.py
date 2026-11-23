import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from core.errors import AppErrorCode, ValidationAppException
from platform.features.billing.subscription.subscription.domain.schemas import (
    SubscriptionSchema,
    UpdateSubscriptionSchema,
)
from platform.features.billing.subscription.subscription.application.use_cases import (
    UpdateSubscriptionUseCase,
)
from platform.features.billing.subscription.subscription.infrastructure import neurana_catalog


def _plan(**over) -> SubscriptionSchema:
    data = dict(
        id=uuid.uuid4(),
        name='Pro',
        price=Decimal('10.00'),
        currency='USD',
        code='PRO',
        is_active=True,
    )
    data.update(over)
    return SubscriptionSchema(**data)


class OverlayCatalogPricesTests(SimpleTestCase):
    def test_linked_plan_takes_the_service_price(self):
        service_id = uuid.uuid4()
        plan = _plan(
            catalog_service_id=service_id,
            catalog_service_code='',
            price=Decimal('10.00'),
            currency='USD',
        )
        service = {
            'id': str(service_id),
            'code': 'WASE01',
            'name': 'Licencia Pro',
            'min_billing_base': '80.50',
            'currency': 'cop',
            'is_active': True,
        }
        persisted = []
        with patch.object(neurana_catalog, 'fetch_service', return_value=service), \
                patch.object(neurana_catalog, '_persist', side_effect=persisted.append):
            updated = neurana_catalog.overlay_catalog_prices([plan])

        self.assertEqual(updated[0].price, Decimal('80.50'))
        self.assertEqual(updated[0].currency, 'COP')
        self.assertEqual(updated[0].catalog_service_code, 'WASE01')
        self.assertEqual(updated[0].catalog_service_name, 'Licencia Pro')
        self.assertEqual(len(persisted), 1)

    def test_catalog_outage_keeps_the_snapshot(self):
        plan = _plan(catalog_service_id=uuid.uuid4(), price=Decimal('15.00'))
        with patch.object(neurana_catalog, 'fetch_service', return_value=None):
            updated = neurana_catalog.overlay_catalog_prices([plan])
        self.assertEqual(updated[0].price, Decimal('15.00'))


class _Repo:
    def update(self, plan_id, data):
        return data


def _reject(_service_id):
    raise ValidationAppException(AppErrorCode.SUB_CATALOG_SERVICE)


class UpdateFromCatalogTests(SimpleTestCase):
    def test_update_copies_the_service_price(self):
        service_id = uuid.uuid4()
        use_case = UpdateSubscriptionUseCase(
            _Repo(),
            catalog_services=lambda _id: {
                'min_billing_base': Decimal('40.00'),
                'currency': 'COP',
                'code': 'WASE02',
                'name': 'Licencia anual',
            },
        )
        data = UpdateSubscriptionSchema(catalog_service_id=service_id, name='Pro')
        saved = use_case.execute(uuid.uuid4(), data)
        self.assertEqual(saved.price, Decimal('40.00'))
        self.assertEqual(saved.currency, 'COP')
        self.assertEqual(saved.catalog_service_code, 'WASE02')

    def test_missing_service_is_rejected(self):
        use_case = UpdateSubscriptionUseCase(_Repo(), catalog_services=_reject)
        with self.assertRaises(ValidationAppException) as caught:
            use_case.execute(
                uuid.uuid4(),
                UpdateSubscriptionSchema(catalog_service_id=uuid.uuid4()),
            )
        self.assertEqual(caught.exception.code, AppErrorCode.SUB_CATALOG_SERVICE)
