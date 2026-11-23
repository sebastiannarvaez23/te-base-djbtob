"""Adaptador del catálogo de funcionalidades: lotes por audiencia y visibilidad."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from handbook.features.docs.content.page.infrastructure import features

pytestmark = pytest.mark.unit


def _revision(audience, client=None, admin=None):
    return SimpleNamespace(audience=audience, client_feature_id=client, admin_feature_id=admin)


def _models():
    return {'wms': MagicMock(), 'admin': MagicMock()}


def test_feature_model_by_audience():
    from platform.features.security.access.functionalities.models import Functionality
    from platform.features.security.access.roles.models import AdminFeature

    assert features.feature_model('wms') is Functionality
    assert features.feature_model('admin') is AdminFeature
    assert features.feature_model('public') is None


def test_keys_batch_one_query_per_audience_and_hide_inactive():
    active, inactive, admin_id = uuid4(), uuid4(), uuid4()
    models = _models()
    active_rows = models['wms'].objects.filter.return_value
    active_rows.filter.return_value.values_list.return_value = [(active, 'orders.view')]
    models['admin'].objects.filter.return_value.filter.return_value.values_list.return_value = []

    revisions = [
        _revision('wms', active), _revision('wms', inactive),
        _revision('admin', admin=admin_id), _revision('public'),
    ]
    with patch.object(features, 'feature_model', side_effect=models.get):
        keys = features.active_feature_keys(revisions)

    assert keys == {active: 'orders.view'}
    models['wms'].objects.filter.assert_called_once_with(is_active=True)
    assert active_rows.filter.call_args.kwargs == {'pk__in': {active, inactive}}
    assert features.readable_feature(revisions[0], keys) == (True, 'orders.view')
    assert features.readable_feature(revisions[1], keys) == (False, None)
    assert features.readable_feature(revisions[2], keys) == (False, None)
    assert features.readable_feature(revisions[3], keys) == (True, None)


def test_keys_skip_queries_without_bound_features():
    with patch.object(features, 'feature_model') as model:
        assert features.active_feature_keys([_revision('public')]) == {}
    model.assert_not_called()


def test_active_key_only_for_audiences_with_catalog():
    models = _models()
    rows = models['wms'].objects.filter.return_value.filter.return_value
    rows.values_list.return_value.first.return_value = 'orders.view'
    with patch.object(features, 'feature_model', side_effect=models.get):
        assert features.active_key('wms', uuid4()) == 'orders.view'
        assert features.active_key('public', uuid4()) is None


def test_feature_label_includes_inactive_features():
    models = _models()
    models['admin'].objects.filter.return_value.values_list.return_value.first.side_effect = [
        ('Bandeja', 'support.inbox'), None,
    ]
    with patch.object(features, 'feature_model', side_effect=models.get):
        assert features.feature_label('admin', uuid4()) == 'Bandeja · support.inbox'
        assert features.feature_label('admin', uuid4()) == ''
        assert features.feature_label('admin', None) == ''
        assert features.feature_label('public', uuid4()) == ''
    models['admin'].objects.filter.return_value.values_list.assert_called_with('label', 'key')


def test_bound_to_key_matches_both_audiences():
    models = _models()
    with patch.object(features, 'feature_model', side_effect=models.get):
        condition = features.bound_to_key('orders.view')
    assert condition.connector == 'OR'
    assert len(condition.children) == 2
    for audience in ('wms', 'admin'):
        models[audience].objects.filter.return_value.filter.assert_called_once_with(key='orders.view')


@pytest.mark.parametrize('query, filtered', [('', False), ('ped', True)])
def test_search_features_filters_and_orders(query, filtered):
    models = _models()
    rows = models['wms'].objects.filter.return_value.select_related.return_value
    with patch.object(features, 'feature_model', side_effect=models.get):
        features.search_features('wms', query)
    assert rows.filter.called is filtered
    ordered = rows.filter.return_value if filtered else rows
    ordered.order_by.assert_called_once_with('key')


def test_search_features_filters_by_category():
    models = _models()
    rows = models['wms'].objects.filter.return_value.select_related.return_value
    with patch.object(features, 'feature_model', side_effect=models.get):
        features.search_features('wms', '', category='api')
    rows.filter.assert_called_once_with(category='api')
    rows.filter.return_value.order_by.assert_called_once_with('key')


def test_feature_category_reads_active_row():
    models = _models()
    rows = models['wms'].objects.filter.return_value.filter.return_value
    rows.values_list.return_value.first.return_value = 'api'
    with patch.object(features, 'feature_model', side_effect=models.get):
        assert features.feature_category('wms', uuid4()) == 'api'
        assert features.feature_category('public', uuid4()) is None
