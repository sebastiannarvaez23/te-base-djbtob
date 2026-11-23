"""Unit tests — code / category filters of the functionality catalogs (no DB)."""
from unittest.mock import MagicMock

import pytest

from platform.features.security.access.functionalities.presentation.queries import FunctionalityQuery
from platform.features.security.access.roles.application.catalog_use_cases import ListAdminCatalogFeaturesUseCase
from platform.features.security.access.roles.presentation.queries import CatalogFeatureListQuery

QUERIES = [FunctionalityQuery, CatalogFeatureListQuery]


@pytest.mark.unit
@pytest.mark.parametrize('query_cls', QUERIES)
class TestFeatureListQuery:

    def test_accepts_key_and_category(self, query_cls):
        query, err = query_cls({'key': 'orders.read', 'category': 'api', 'label': 'Pedidos'}).parse()
        assert err is None
        assert query.filters['key'] == 'orders.read'
        assert query.filters['category'] == 'api'

    def test_rejects_unknown_category(self, query_cls):
        _, err = query_cls({'category': 'billing'}).parse()
        assert err is not None

    def test_rejects_key_with_spaces(self, query_cls):
        _, err = query_cls({'key': 'orders read'}).parse()
        assert err is not None


@pytest.mark.unit
def test_admin_use_case_forwards_key_and_category():
    repo = MagicMock()
    ListAdminCatalogFeaturesUseCase(repo).execute(
        page=1, page_size=20, module_code='ORDERS', label='Ver', key='orders.', category='ai',
    )
    repo.list_features_paginated.assert_called_once_with(
        page=1, page_size=20, module_code='ORDERS', module_id=None,
        label='Ver', key='orders.', category='ai',
    )
