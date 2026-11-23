"""Unit tests for quota enforcement registry and reconciliation."""
import uuid
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.access.enforcement import (
    enforcement_registry,
    IQuotaEntityAdapter,
    USERS_QUOTA_FEATURE,
)
from core.access.reconcile import reconcile_company_quotas, reconcile_feature_quota


@contextmanager
def _noop_atomic():
    yield


class _FakeAdapter(IQuotaEntityAdapter):
    feature_key = 'test.quota.feature'

    def __init__(self):
        self.active: list[uuid.UUID] = []
        self.protected: set[uuid.UUID] = set()
        self.deactivated: list[uuid.UUID] = []

    def count_active(self, company_id: str) -> int:
        return len(self.active)

    def list_active_entity_ids(self, company_id: str) -> list[uuid.UUID]:
        return list(self.active)

    def protected_entity_ids(self, company_id: str) -> set[uuid.UUID]:
        return set(self.protected)

    def deactivate(self, entity_id: uuid.UUID, company_id: str) -> None:
        self.deactivated.append(entity_id)
        self.active = [x for x in self.active if x != entity_id]


class TestReconcileFeatureQuota(TestCase):
    def setUp(self):
        self.adapter = _FakeAdapter()
        enforcement_registry.register(self.adapter)
        self.company_id = str(uuid.uuid4())

    def tearDown(self):
        enforcement_registry._adapters.pop('test.quota.feature', None)

    def test_no_excess_no_deactivation(self):
        u1, u2 = uuid.uuid4(), uuid.uuid4()
        self.adapter.active = [u1, u2]
        result = reconcile_feature_quota(self.company_id, 'test.quota.feature', 5)
        self.assertEqual(result.deactivated_count, 0)

    def test_deactivates_excess_skipping_protected(self):
        admin = uuid.uuid4()
        others = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        self.adapter.active = [admin] + others
        self.adapter.protected = {admin}
        with patch('core.access.reconcile.transaction.atomic', _noop_atomic):
            result = reconcile_feature_quota(self.company_id, 'test.quota.feature', 1)
        self.assertEqual(result.deactivated_count, 3)
        self.assertNotIn(admin, self.adapter.deactivated)
        self.assertEqual(len(self.adapter.active), 1)
        self.assertEqual(self.adapter.active[0], admin)

    def test_deactivates_newest_first(self):
        u1, u2, u3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.adapter.active = [u1, u2, u3]
        with patch('core.access.reconcile.transaction.atomic', _noop_atomic):
            reconcile_feature_quota(self.company_id, 'test.quota.feature', 1)
        self.assertEqual(set(self.adapter.deactivated), {u2, u3})


class TestReconcileCompanyQuotas(TestCase):
    def tearDown(self):
        enforcement_registry._adapters.pop(USERS_QUOTA_FEATURE, None)

    @patch('platform.features.billing.quota.quota_enforcement.infrastructure.limit_loader.load_subscription_limit_map')
    def test_only_lifetime_with_adapter(self, mock_load_limits):
        from client.features.security.lifecycle.registration.quota_adapters import CompanyUsersQuotaAdapter

        enforcement_registry.register(CompanyUsersQuotaAdapter())
        company_id = uuid.uuid4()
        sub_id = uuid.uuid4()

        limits = {
            USERS_QUOTA_FEATURE: {'max': 1, 'type': 'lifetime'},
            'orders.create': {'max': 100, 'type': 'lifetime'},
            'api.calls': {'max': 10, 'type': 'daily'},
        }
        mock_load_limits.return_value = limits

        adapter = enforcement_registry.get(USERS_QUOTA_FEATURE)
        admin_id = uuid.uuid4()
        other_id = uuid.uuid4()
        with patch('core.access.reconcile.transaction.atomic', _noop_atomic):
            with patch.object(adapter, 'list_active_entity_ids', return_value=[admin_id, other_id]):
                with patch.object(adapter, 'protected_entity_ids', return_value={admin_id}):
                    with patch.object(adapter, 'deactivate') as mock_deact:
                        result = reconcile_company_quotas(company_id, sub_id, limits=limits)
                    mock_deact.assert_called_once_with(other_id, str(company_id))
                    self.assertEqual(len(result.features), 1)
