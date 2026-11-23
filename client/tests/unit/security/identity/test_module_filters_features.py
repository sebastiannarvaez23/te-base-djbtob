"""Warehouse module-filter toolbar keys: spaces OR topology."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import pytest

from client.features.security.identity.module_filters.presentation import api as filters_api

pytestmark = pytest.mark.unit

SPACES = 'warehouse.spaces.toolbar-avanced-filters'
TOPOLOGY = 'warehouse.topology.toolbar-avanced-filters'


class TestPreferredWarehouseFiltersFeature(TestCase):

    def test_without_role_defaults_to_spaces(self):
        request = SimpleNamespace(user=SimpleNamespace(rol=None, rol_id=None))
        self.assertEqual(filters_api._preferred_warehouse_filters_feature(request), SPACES)

    @patch('core.access.role_cache.RoleFeatureCache.get_or_load', return_value={TOPOLOGY})
    def test_topology_only_role_uses_topology_key(self, _cache):
        request = SimpleNamespace(user=SimpleNamespace(rol_id='role-1', rol=None))
        self.assertEqual(filters_api._preferred_warehouse_filters_feature(request), TOPOLOGY)

    @patch('core.access.role_cache.RoleFeatureCache.get_or_load', return_value={SPACES})
    def test_spaces_only_role_uses_spaces_key(self, _cache):
        request = SimpleNamespace(user=SimpleNamespace(rol_id='role-1', rol=None))
        self.assertEqual(filters_api._preferred_warehouse_filters_feature(request), SPACES)

    @patch('core.access.role_cache.RoleFeatureCache.get_or_load', return_value=set())
    def test_neither_key_falls_back_to_spaces(self, _cache):
        request = SimpleNamespace(user=SimpleNamespace(rol_id='role-1', rol=None))
        self.assertEqual(filters_api._preferred_warehouse_filters_feature(request), SPACES)

    def test_non_warehouse_module_returns_none(self):
        self.assertIsNone(filters_api._warehouse_filters_feature('orders'))
        self.assertIsNone(filters_api._warehouse_filters_feature('receiving.receipts'))
        self.assertIsNone(filters_api._warehouse_filters_feature('receiving.putaway'))
        self.assertEqual(
            filters_api._warehouse_filters_feature('warehouse'),
            SPACES,
        )
