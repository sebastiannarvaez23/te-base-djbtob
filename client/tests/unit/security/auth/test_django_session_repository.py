"""Unit tests for DjangoSessionRepository.build_menu (sidebar filter)."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from client.features.security.lifecycle.auth.infrastructure.repositories import DjangoSessionRepository


def _module(*, code: str, sidebar: bool = True):
    module = MagicMock()
    module.id = uuid.uuid4()
    module.code = code
    module.name = code
    module.icon = 'bx-grid'
    module.route = f'/{code}'
    module.is_sidebar = sidebar
    module.section.code = 'ops'
    module.section.name = 'Operaciones'
    module.section.order = 1
    module.order = 1
    return module


class TestDjangoSessionRepositoryBuildMenu(TestCase):

    @patch('core.module_codes.module_catalog_index', return_value={'orders': 'orders'})
    @patch('platform.features.security.access.modules.models.Module')
    @patch('client.features.security.lifecycle.registration.models.RolModule')
    @patch('client.features.security.lifecycle.registration.models.RolFeature')
    def test_menu_filters_active_sidebar_modules(self, MockRF, MockRM, MockModule, _catalog):
        rol = MagicMock()
        feature = MagicMock()
        feature.key = 'orders.create'
        feature.module.code = 'orders'
        rf = MagicMock()
        rf.feature = feature

        orders = _module(code='orders')
        MockRF.objects.filter.return_value.select_related.return_value = [rf]
        MockRM.objects.filter.return_value.values_list.return_value = []
        MockModule.objects.filter.return_value.select_related.return_value = [orders]

        menu, features = DjangoSessionRepository().build_menu(rol)

        self.assertEqual(features, ['orders.create'])
        self.assertEqual([item.code for item in menu], ['orders'])
        MockModule.objects.filter.assert_called_once_with(
            code__in=['orders'],
            is_active=True,
            is_sidebar=True,
            section__is_active=True,
        )

    @patch(
        'platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access',
        return_value=({'connectors.sap'}, {'connectors'}),
    )
    @patch('core.module_codes.module_catalog_index', return_value={'orders': 'orders', 'connectors': 'connectors'})
    @patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality')
    @patch('platform.features.billing.subscription.subscription.models.SubscriptionModule')
    @patch('platform.features.security.access.modules.models.Module')
    @patch('client.features.security.lifecycle.registration.models.RolModule')
    @patch('client.features.security.lifecycle.registration.models.RolFeature')
    def test_menu_unions_plan_and_complement(
        self, MockRF, MockRM, MockModule, MockSubModule, MockSubFeature, _catalog, _complements,
    ):
        rol = MagicMock()
        orders_feature = MagicMock()
        orders_feature.key = 'orders.create'
        orders_feature.module.code = 'orders'
        sap_feature = MagicMock()
        sap_feature.key = 'connectors.sap'
        sap_feature.module.code = 'connectors'
        orders_link = MagicMock()
        orders_link.feature = orders_feature
        sap_link = MagicMock()
        sap_link.feature = sap_feature
        MockRF.objects.filter.return_value.select_related.return_value = [orders_link, sap_link]
        MockRM.objects.filter.return_value.values_list.return_value = []
        MockSubModule.objects.filter.return_value.values_list.return_value = ['orders']
        MockSubFeature.objects.filter.return_value.values_list.return_value = ['orders.create']
        orders = _module(code='orders')
        connectors = _module(code='connectors')
        MockModule.objects.filter.return_value.select_related.return_value = [orders, connectors]

        menu, features = DjangoSessionRepository().build_menu(rol, 'plan-1', 'company-1')

        self.assertEqual(features, ['orders.create', 'connectors.sap'])
        self.assertEqual([item.code for item in menu], ['orders', 'connectors'])

    @patch(
        'platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access',
        return_value=({'connectors.sap'}, {'connectors'}),
    )
    @patch('core.module_codes.module_catalog_index', return_value={'orders': 'orders', 'connectors': 'connectors'})
    @patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality')
    @patch('platform.features.billing.subscription.subscription.models.SubscriptionModule')
    @patch('platform.features.security.access.modules.models.Module')
    @patch('client.features.security.lifecycle.registration.models.RolModule')
    @patch('client.features.security.lifecycle.registration.models.RolFeature')
    def test_administrator_receives_complement_without_role_grant(
        self, MockRF, MockRM, MockModule, MockSubModule, MockSubFeature, _catalog, _complements,
    ):
        rol = MagicMock()
        rol.name = 'Administrator'
        orders_feature = MagicMock()
        orders_feature.key = 'orders.create'
        orders_feature.module.code = 'orders'
        orders_link = MagicMock()
        orders_link.feature = orders_feature
        MockRF.objects.filter.return_value.select_related.return_value = [orders_link]
        MockRM.objects.filter.return_value.values_list.return_value = []
        MockSubModule.objects.filter.return_value.values_list.return_value = ['orders']
        MockSubFeature.objects.filter.return_value.values_list.return_value = ['orders.create']
        orders = _module(code='orders')
        connectors = _module(code='connectors')
        MockModule.objects.filter.return_value.select_related.return_value = [orders, connectors]

        menu, features = DjangoSessionRepository().build_menu(rol, 'plan-1', 'company-1')

        self.assertEqual(features, ['orders.create', 'connectors.sap'])
        self.assertEqual([item.code for item in menu], ['orders', 'connectors'])

    def test_no_role_returns_empty(self):
        menu, features = DjangoSessionRepository().build_menu(None)
        self.assertEqual(menu, [])
        self.assertEqual(features, [])
