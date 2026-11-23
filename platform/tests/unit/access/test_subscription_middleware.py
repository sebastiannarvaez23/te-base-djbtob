"""SubscriptionMiddleware loads the entitled period and stamps the request."""
import uuid
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.db.models import Q

from core.access.middleware import SubscriptionMiddleware


def _assert_entitled_lookup(test, MockCS, company_id):
    args, kwargs = MockCS.objects.filter.call_args
    test.assertEqual(kwargs['company_id'], company_id)
    test.assertTrue(kwargs['subscription__is_active'])
    test.assertTrue(any(isinstance(arg, Q) for arg in args))


class TestSubscriptionMiddleware(TestCase):

    def _request(self, *, tenant=True, cookies=None):
        request = SimpleNamespace(COOKIES=cookies or {}, META={})
        if tenant:
            request.tenant = SimpleNamespace(id=uuid.uuid4())
        else:
            request.tenant = None
        return request

    def test_without_tenant_leaves_period_unset(self):
        seen = []
        mw = SubscriptionMiddleware(lambda req: seen.append(req) or req)
        request = self._request(tenant=False)
        mw(request)
        self.assertIsNone(request.company_subscription_id)
        self.assertIsNone(request.subscription_id)
        self.assertEqual(seen, [request])

    @patch('core.access.hooks.notify_subscription_expiry')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('core.access.subscription.SubscriptionCache')
    def test_cache_miss_loads_active_period_and_stamps_request(
        self, MockCache, MockCS, mock_notify,
    ):
        MockCache.get_subscription_id.return_value = None
        MockCache.get_acquisition_id.return_value = None
        MockCS.Status.ACTIVE = 'active'
        period_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        cs = MagicMock(id=period_id, subscription_id=plan_id)
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = cs

        request = self._request()
        SubscriptionMiddleware(lambda req: req)(request)

        _assert_entitled_lookup(self, MockCS, str(request.tenant.id))
        self.assertEqual(request.company_subscription_id, str(period_id))
        self.assertEqual(request.subscription_id, str(plan_id))
        self.assertIs(request.subscription, cs)
        MockCache.set_acquisition_id.assert_called_once_with(
            str(request.tenant.id), str(period_id),
        )
        mock_notify.assert_called_once_with(str(request.tenant.id), cs)

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('core.access.subscription.SubscriptionCache')
    def test_cache_hit_does_not_query_orm(self, MockCache, MockCS):
        plan_id = str(uuid.uuid4())
        period_id = str(uuid.uuid4())
        MockCache.get_subscription_id.return_value = plan_id
        MockCache.get_acquisition_id.return_value = period_id

        request = self._request()
        SubscriptionMiddleware(lambda req: req)(request)

        MockCS.objects.filter.assert_not_called()
        self.assertEqual(request.subscription_id, plan_id)
        self.assertEqual(request.company_subscription_id, period_id)

    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('core.access.subscription.SubscriptionCache')
    def test_cache_miss_without_period_caches_empty(self, MockCache, MockCS):
        MockCache.get_subscription_id.return_value = None
        MockCache.get_acquisition_id.return_value = None
        MockCS.Status.ACTIVE = 'active'
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = None

        request = self._request()
        SubscriptionMiddleware(lambda req: req)(request)

        MockCache.set_subscription_id.assert_called_once_with(str(request.tenant.id), '')
        MockCache.set_acquisition_id.assert_called_once_with(str(request.tenant.id), '')
        self.assertIsNone(request.company_subscription_id)
        self.assertIsNone(request.subscription_id)

    @patch('core.access.subscription.SubscriptionCache')
    def test_load_failure_never_breaks_the_request(self, MockCache):
        MockCache.get_subscription_id.side_effect = RuntimeError('redis down')
        request = self._request()
        returned = SubscriptionMiddleware(lambda req: req)(request)
        self.assertIs(returned, request)
        self.assertIsNone(request.company_subscription_id)

    @patch('core.access.hooks.notify_subscription_expiry')
    @patch('platform.features.billing.subscription.subscription.models.CompanySubscription')
    @patch('core.access.subscription.SubscriptionCache')
    @patch('core.access.middleware.SubscriptionMiddleware._company_id_from_client_jwt')
    def test_spa_host_uses_jwt_company_not_missing_tenant(
        self, mock_jwt_company, MockCache, MockCS, mock_notify,
    ):
        """En app.* (sin tenant) la empresa sale del JWT cliente."""
        company_id = str(uuid.uuid4())
        mock_jwt_company.return_value = company_id
        MockCache.get_subscription_id.return_value = None
        MockCache.get_acquisition_id.return_value = None
        MockCS.Status.ACTIVE = 'active'
        period_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        cs = MagicMock(id=period_id, subscription_id=plan_id)
        MockCS.objects.filter.return_value.select_related.return_value \
            .order_by.return_value.first.return_value = cs

        request = self._request(tenant=False)
        SubscriptionMiddleware(lambda req: req)(request)

        _assert_entitled_lookup(self, MockCS, company_id)
        self.assertEqual(request.subscription_id, str(plan_id))
        self.assertEqual(request.company_subscription_id, str(period_id))
