"""Tests for lifetime validator with enforcement registry."""
import uuid
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.access.checker import AccessChecker
from core.access.enforcement import enforcement_registry, IQuotaEntityAdapter
from core.access.validators.lifetime import LifetimeValidator, _FAIL_CLOSED_USAGE


class _CountAdapter(IQuotaEntityAdapter):
    feature_key = 'test.enforcement.count'

    def __init__(self, count: int):
        self._count = count

    def count_active(self, company_id: str) -> int:
        return self._count

    def list_active_entity_ids(self, company_id: str) -> list:
        return []

    def protected_entity_ids(self, company_id: str) -> set:
        return set()

    def deactivate(self, entity_id, company_id: str) -> None:
        pass


class TestLifetimeValidatorEnforcement(TestCase):
    def tearDown(self):
        enforcement_registry._adapters.pop('test.enforcement.count', None)

    def test_reads_count_from_registry(self):
        enforcement_registry.register(_CountAdapter(3))
        validator = LifetimeValidator()
        self.assertEqual(
            validator.get_current_usage('co-1', 'test.enforcement.count'),
            3,
        )

    def test_fail_closed_when_count_raises(self):
        enforcement_registry.register(_CountAdapter(0))
        with patch.object(
            enforcement_registry,
            'count_active',
            return_value=None,
        ):
            validator = LifetimeValidator()
            self.assertEqual(
                validator.get_current_usage('co-1', 'test.enforcement.count'),
                _FAIL_CLOSED_USAGE,
            )


class TestEnsureQuotaOrRaise(TestCase):
    FEATURE = 'security.users.create'

    def tearDown(self):
        enforcement_registry._adapters.pop(self.FEATURE, None)

    @patch('core.access.checker.SubscriptionCache')
    def test_raises_subscription_exception_when_denied(self, MockCache):
        from core.errors.codes import AppErrorCode
        from core.errors.exceptions import SubscriptionException

        adapter = _CountAdapter(1)
        adapter.feature_key = self.FEATURE
        enforcement_registry.register(adapter)

        company = MagicMock()
        company.id = uuid.uuid4()
        MockCache.get_subscription_id.return_value = 'sub-1'
        MockCache.get_features.return_value = {self.FEATURE}
        MockCache.get_limits.return_value = {
            self.FEATURE: {'max': 1, 'type': 'lifetime'},
        }

        with self.assertRaises(SubscriptionException) as ctx:
            AccessChecker.ensure_quota_or_raise(company, self.FEATURE)
        self.assertEqual(ctx.exception.code, AppErrorCode.SUB_QUOTA_EXCEEDED)
