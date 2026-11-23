"""Unit tests — AccessControlScopeCatalog (plan ∩ role, no DB)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from client.features.integrations.oauth.client.infrastructure.scope_catalog import AccessControlScopeCatalog

MODULE = 'client.features.integrations.oauth.client.infrastructure.scope_catalog'


def _row(key: str):
    return SimpleNamespace(key=key, label=f'Label {key}', module=SimpleNamespace(code='orders', name='Orders'))


@pytest.fixture
def catalog_env():
    rows = [_row('api.orders.read'), _row('api.orders.write')]
    queryset = MagicMock()
    queryset.filter.return_value.select_related.return_value.order_by.return_value = rows
    with patch(f'{MODULE}.AccessChecker.enabled_features', return_value={'api.orders.read', 'api.orders.write'}) as enabled, \
            patch(f'{MODULE}.Functionality') as functionality, \
            patch(f'{MODULE}.RoleFeatureCache.get_or_load', return_value={'api.orders.read'}) as role_keys:
        functionality.objects = queryset
        yield SimpleNamespace(enabled=enabled, queryset=queryset, role_keys=role_keys)


def _user(rol_id='r1', active=True):
    return SimpleNamespace(rol_id=rol_id, rol=SimpleNamespace(id=rol_id, is_active=active) if rol_id else None)


@pytest.mark.unit
class TestAccessControlScopeCatalog:

    def test_tenant_scopes_filter_api_category_and_plan(self, catalog_env):
        company = SimpleNamespace(id='c1')
        scopes = AccessControlScopeCatalog(company).tenant_scopes()
        assert [s.key for s in scopes] == ['api.orders.read', 'api.orders.write']
        assert scopes[0].module_name == 'Orders'
        kwargs = catalog_env.queryset.filter.call_args.kwargs
        assert kwargs['category'] == 'api'
        assert kwargs['key__in'] == {'api.orders.read', 'api.orders.write'}
        assert kwargs['is_active'] is True

    def test_tenant_scopes_are_memoized(self, catalog_env):
        catalog = AccessControlScopeCatalog(SimpleNamespace(id='c1'))
        catalog.tenant_scopes()
        catalog.tenant_scopes()
        assert catalog_env.enabled.call_count == 1

    def test_no_plan_means_no_scopes(self, catalog_env):
        catalog_env.enabled.return_value = set()
        assert AccessControlScopeCatalog(SimpleNamespace(id='c1'), _user()).grantable_scopes() == []
        catalog_env.queryset.filter.assert_not_called()

    def test_no_company_means_no_scopes(self, catalog_env):
        assert AccessControlScopeCatalog(None).tenant_scopes() == []

    def test_grantable_is_restricted_by_role(self, catalog_env):
        scopes = AccessControlScopeCatalog(SimpleNamespace(id='c1'), _user()).grantable_scopes()
        assert [s.key for s in scopes] == ['api.orders.read']
        catalog_env.role_keys.assert_called_once_with('r1')

    def test_user_without_role_gets_plan_scopes(self, catalog_env):
        scopes = AccessControlScopeCatalog(SimpleNamespace(id='c1'), _user(rol_id=None)).grantable_scopes()
        assert [s.key for s in scopes] == ['api.orders.read', 'api.orders.write']

    def test_inactive_role_grants_nothing(self, catalog_env):
        scopes = AccessControlScopeCatalog(SimpleNamespace(id='c1'), _user(active=False)).grantable_scopes()
        assert scopes == []

    def test_without_actor_nothing_is_grantable(self, catalog_env):
        assert AccessControlScopeCatalog(SimpleNamespace(id='c1')).grantable_scopes() == []

    def test_api_scope_keys_filters_by_api_category_only(self, catalog_env):
        catalog_env.queryset.filter.return_value.values_list.return_value = ['api.orders.read']
        keys = AccessControlScopeCatalog(None).api_scope_keys(['api.orders.read', 'orders.view'])
        assert keys == {'api.orders.read'}
        assert catalog_env.queryset.filter.call_args.kwargs == {
            'category': 'api', 'key__in': {'api.orders.read', 'orders.view'},
        }

    def test_api_scope_keys_skips_query_without_keys(self, catalog_env):
        assert AccessControlScopeCatalog(None).api_scope_keys([]) == set()
        catalog_env.queryset.filter.assert_not_called()
