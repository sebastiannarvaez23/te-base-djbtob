"""Access ceiling: plan features union active complement licenses."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.access.checker import AccessChecker
from core.errors.codes import AppErrorCode
from platform.features.billing.complement.entitlement.infrastructure.active import (
    active_complement_access,
)


class TestActiveComplementQuery(TestCase):

    @patch('core.access.subscription.SubscriptionCache.set_complements')
    @patch('core.access.subscription.SubscriptionCache.get_complements', return_value=None)
    @patch('platform.features.billing.complement.entitlement.infrastructure.active.CompanyComplement')
    def test_only_open_active_licenses_are_read(self, model, _cached, _store):
        functionality = MagicMock()
        module = MagicMock()
        model.Status.ACTIVE = 'active'
        model.objects.filter.side_effect = [functionality, module]
        functionality.filter.return_value = functionality
        module.filter.return_value = module
        functionality.values_list.return_value = [('connectors.sap', 'connectors')]
        module.values_list.return_value = []

        keys, modules = active_complement_access('company-1')

        self.assertEqual(keys, {'connectors.sap'})
        self.assertEqual(modules, {'connectors'})
        kwargs = model.objects.filter.call_args_list[0].kwargs
        self.assertEqual(kwargs['status'], 'active')
        self.assertEqual(kwargs['functionality__is_active'], True)
        self.assertEqual(kwargs['functionality__offering'], 'complement')
        self.assertTrue(functionality.filter.called)

    @patch('core.access.subscription.SubscriptionCache.set_complements')
    @patch('core.access.subscription.SubscriptionCache.get_complements', return_value=None)
    @patch('platform.features.billing.complement.entitlement.infrastructure.active.Functionality')
    @patch('platform.features.billing.complement.entitlement.infrastructure.active.CompanyComplement')
    def test_module_license_adds_module_code_and_its_feature_keys(self, model, functionality, _cached, _store):
        functionality_licenses = MagicMock()
        module_licenses = MagicMock()
        model.Status.ACTIVE = 'active'
        model.objects.filter.side_effect = [functionality_licenses, module_licenses]
        functionality_licenses.filter.return_value = functionality_licenses
        module_licenses.filter.return_value = module_licenses
        functionality_licenses.values_list.return_value = []
        module_id = uuid.uuid4()
        module_licenses.values_list.return_value = [(module_id, 'connectors')]
        functionality.objects.filter.return_value.values_list.return_value = [
            (module_id, 'connectors.sap'),
        ]

        keys, modules = active_complement_access('company-1')

        self.assertEqual(keys, {'connectors.sap'})
        self.assertEqual(modules, {'connectors'})

    @patch('platform.features.billing.complement.entitlement.infrastructure.active.CompanyComplement')
    @patch(
        'core.access.subscription.SubscriptionCache.get_complements',
        return_value=({'connectors.sap'}, {'connectors'}),
    )
    def test_cached_license_skips_the_database(self, _cached, model):
        keys, modules = active_complement_access('company-1')

        self.assertEqual(keys, {'connectors.sap'})
        self.assertEqual(modules, {'connectors'})
        model.objects.filter.assert_not_called()


class TestLoadFeaturesUnion(TestCase):

    @patch('platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access')
    @patch('platform.features.billing.subscription.subscription.models.SubscriptionFunctionality')
    @patch('platform.features.billing.subscription.subscription.models.Subscription')
    @patch('core.access.checker.SubscriptionCache')
    def test_unions_plan_and_complement_keys(self, cache, subscription, plan_features, complements):
        subscription.objects.filter.return_value.exists.return_value = True
        plan_features.objects.filter.return_value.values_list.return_value = ['orders.create']
        complements.return_value = ({'connectors.sap'}, {'connectors'})

        keys = AccessChecker._load_features('sub-1', 'company-1')

        self.assertEqual(keys, {'orders.create', 'connectors.sap'})
        cache.set_features.assert_called_once_with('company-1', {'orders.create', 'connectors.sap'})

    @patch('platform.features.billing.complement.entitlement.infrastructure.active.active_complement_access')
    @patch('core.access.checker.SubscriptionCache')
    def test_company_without_plan_never_reads_complements(self, cache, complements):
        cache.get_subscription_id.return_value = ''
        company = MagicMock()
        company.id = uuid.uuid4()

        result = AccessChecker.check_feature(company, 'connectors.sap')

        self.assertFalse(result.is_allowed)
        self.assertEqual(result.error_code, AppErrorCode.SUB_NO_ACTIVE)
        complements.assert_not_called()
