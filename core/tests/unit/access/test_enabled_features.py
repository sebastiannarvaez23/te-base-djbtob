"""Unit tests — AccessChecker.enabled_features (cache first, DB fallback)."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.access.checker import AccessChecker

CHECKER = 'core.access.checker'
COMPANY = SimpleNamespace(id='c1')


@pytest.mark.unit
class TestEnabledFeatures:

    def test_returns_cached_plan_features(self):
        with patch(f'{CHECKER}.SubscriptionCache.get_subscription_id', return_value='s1'), \
                patch(f'{CHECKER}.SubscriptionCache.get_features', return_value={'api.orders.read'}), \
                patch.object(AccessChecker, '_load_features') as load:
            assert AccessChecker.enabled_features(COMPANY) == {'api.orders.read'}
        load.assert_not_called()

    def test_loads_features_on_cache_miss(self):
        with patch(f'{CHECKER}.SubscriptionCache.get_subscription_id', return_value='s1'), \
                patch(f'{CHECKER}.SubscriptionCache.get_features', return_value=None), \
                patch.object(AccessChecker, '_load_features', return_value={'orders.create'}) as load:
            assert AccessChecker.enabled_features(COMPANY) == {'orders.create'}
        load.assert_called_once_with('s1', 'c1')

    @pytest.mark.parametrize('cached', ['', None])
    def test_no_active_subscription_is_empty(self, cached):
        with patch(f'{CHECKER}.SubscriptionCache.get_subscription_id', return_value=cached), \
                patch.object(AccessChecker, '_load_subscription_id', return_value=None), \
                patch(f'{CHECKER}.SubscriptionCache.get_features') as get_features:
            assert AccessChecker.enabled_features(COMPANY) == set()
        get_features.assert_not_called()
