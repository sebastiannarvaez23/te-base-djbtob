"""Vistas HTTP del handbook: validación de entrada, envelope y orquestación."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from rest_framework.test import APIRequestFactory

from handbook.core.constants import APPROVE_FEATURE_KEY, PROPOSE_FEATURE_KEY
from handbook.core.viewer import HandbookViewer
from handbook.features.docs.content.catalog.presentation import api
from handbook.features.docs.content.page.domain.schemas import FeatureOptionView
from handbook.features.docs.content.page.infrastructure.memory import MemoryDocumentStore, MemoryMarkdownStore
from handbook.features.docs.governance.change_request.infrastructure.memory import (
    InMemoryChangeRequestRepository,
)

pytestmark = pytest.mark.api

FEATURE = FeatureOptionView(id=uuid4(), key='warehouse.spaces.view', label='Espacios', module='Warehouse', audience='wms')
EDITOR = HandbookViewer.admin(
    user_id=str(uuid4()), features=frozenset({PROPOSE_FEATURE_KEY, APPROVE_FEATURE_KEY}), is_superuser=True,
)
REASON = 'Actualizamos la guía con el flujo vigente.'
factory = APIRequestFactory()


@pytest.fixture
def env():
    state = SimpleNamespace(
        blobs=MemoryMarkdownStore(),
        docs=None,
        requests=InMemoryChangeRequestRepository(),
        viewer=EDITOR,
        audit=MagicMock(),
    )
    state.docs = MemoryDocumentStore([FEATURE])
    with patch.object(api, '_blobs', lambda: state.blobs), \
            patch.object(api, '_documents', lambda blobs=None: state.docs), \
            patch.object(api, '_requests', lambda: state.requests), \
            patch.object(api, 'resolve_viewer', lambda request: state.viewer), \
            patch.object(api, 'audit_log', state.audit), \
            patch.object(api.HandbookAccessAuthentication, 'authenticate', return_value=None), \
            patch('rest_framework.views.APIView.get_throttles', return_value=[]):
        yield state


def _call(view, method='get', path='/', data=None, **kwargs):
    builder = getattr(factory, method)
    request = builder(path, data, format='json') if method != 'get' else builder(path, data or {})
    return view.as_view()(request, **kwargs)


def _page_body(slug='pedidos', **overrides):
    body = {
        'slug': slug,
        'audience': 'public',
        'kind': 'manual',
        'versions': [{'locale': 'es', 'version': '1.0', 'title': 'Pedidos', 'markdown': '# Pedidos'}],
    }
    body.update(overrides)
    return body


def _create(env, slug='pedidos', **overrides):
    response = _call(api.ManagePageListView, 'post', data=_page_body(slug, **overrides))
    assert response.status_code == 201, response.data
    return response.data['data']


def _publish(env, page_id):
    env.docs.publish(UUID(page_id))


def test_create_list_get_and_update_page(env):
    created = _create(env)
    assert created['status'] == 'draft'
    env.audit.assert_called_once()

    listed = _call(api.ManagePageListView, data={'page': 0, 'page_size': 10})
    assert listed.data['data']['total'] == 1
    assert listed.data['data']['total_pages'] == 1
    assert listed.data['message'] == 'Handbook pages loaded.'

    detail = _call(api.ManagePageDetailView, page_id=created['id'])
    assert detail.data['data']['slug'] == 'pedidos'

    updated = _call(api.ManagePageDetailView, 'put', data=_page_body(sort_order=3), page_id=created['id'])
    assert updated.status_code == 200
    assert updated.data['data']['sort_order'] == 3


def test_delete_child_page_and_keep_its_parent(env):
    parent = _create(env, 'raiz')
    child = _create(env, 'hijo', parent_id=parent['id'])
    grandchild = _create(env, 'nieto', parent_id=child['id'])

    blocked = _call(api.ManagePageDetailView, 'delete', page_id=child['id'])
    assert blocked.status_code == 409
    assert blocked.data['error']['code'] == 'HBK_021'

    removed = _call(api.ManagePageDetailView, 'delete', page_id=grandchild['id'])
    assert removed.status_code == 200
    assert removed.data['message'] == 'Handbook page deleted.'
    env.audit.assert_called()

    listed = _call(api.ManagePageListView, data={'page': 0, 'page_size': 10})
    assert {item['slug'] for item in listed.data['data']['items']} == {'raiz', 'hijo'}

    root = _call(api.ManagePageDetailView, 'delete', page_id=parent['id'])
    assert root.status_code == 400
    assert root.data['error']['code'] == 'HBK_020'
    assert _call(api.ManagePageDetailView, 'delete', page_id=str(uuid4())).status_code == 404


def test_invalid_body_and_query_are_rejected_with_400(env):
    assert _call(api.ManagePageListView, 'post', data=_page_body(slug='Bad Slug')).status_code == 400
    assert _call(api.ManagePageListView, 'post', data={**_page_body(), 'extra': 1}).status_code == 400
    assert _call(api.ManagePageListView, data={'page_size': 999}).status_code == 400
    assert _call(api.HandbookHelpView).status_code == 400
    assert _call(api.HandbookTreeView, data={'locale': 'fr'}).status_code == 400
    assert _call(api.HandbookSearchView, data={'q': 'x'}).status_code == 400


def test_reader_endpoints(env):
    created = _create(env, client_feature_id=None)
    _publish(env, created['id'])
    env.viewer = HandbookViewer.anonymous()

    tree = _call(api.HandbookTreeView)
    assert [node['slug'] for node in tree.data['data']] == ['pedidos']
    page = _call(api.HandbookPageView, slug='pedidos', data={'locale': 'es'})
    assert page.data['data']['published_markdown'] == '# Pedidos'
    hits = _call(api.HandbookSearchView, data={'q': 'pedidos'})
    assert [hit['slug'] for hit in hits.data['data']] == ['pedidos']
    assert _call(api.HandbookPageView, slug='otra').status_code == 404


def test_help_endpoint(env):
    created = _create(env, 'espacios', audience='wms', client_feature_id=str(FEATURE.id))
    _publish(env, created['id'])
    env.viewer = HandbookViewer.client(user_id=str(uuid4()), schema_name='acme', features=frozenset({FEATURE.key}))

    found = _call(api.HandbookHelpView, data={'feature_key': FEATURE.key, 'locale': 'en'})
    assert found.status_code == 200
    assert found.data['data']['slug'] == 'espacios'
    assert _call(api.HandbookHelpView, data={'feature_key': 'orders.none'}).status_code == 404


def test_feature_listing(env):
    response = _call(api.ManageFeatureListView, data={'audience': 'wms', 'q': 'espa'})
    assert response.data['data']['total'] == 1
    assert response.data['data']['items'][0]['key'] == FEATURE.key
    assert _call(api.ManageFeatureListView, data={'audience': 'otro'}).status_code == 400


def test_change_request_flow(env):
    created = _create(env)
    submitted = _call(api.ManageChangeRequestListView, 'post', data={'page_id': created['id'], 'reason': REASON})
    assert submitted.status_code == 201
    assert submitted.data['data']['page_slug'] == 'pedidos'
    assert submitted.data['data']['locales'] == ['es']

    pending = _call(api.ManageChangeRequestListView)
    assert pending.data['data']['total'] == 1
    request_id = pending.data['data']['items'][0]['id']

    approved = _call(api.ManageChangeApproveView, 'post', data={'review_note': 'Ok'}, request_id=request_id)
    assert approved.data['data']['status'] == 'approved'
    assert _call(api.ManageChangeRejectView, 'post', data={}, request_id=request_id).status_code == 409


def test_reject_and_permissions(env):
    created = _create(env)
    submitted = _call(api.ManageChangeRequestListView, 'post', data={'page_id': created['id'], 'reason': REASON})
    rejected = _call(api.ManageChangeRejectView, 'post', data={}, request_id=submitted.data['data']['id'])
    assert rejected.data['data']['status'] == 'rejected'

    env.viewer = HandbookViewer.anonymous()
    assert _call(api.ManageChangeRequestListView).status_code in (401, 403)
    assert _call(api.ManagePageListView).status_code in (401, 403)
    assert _call(api.ManageChangeApproveView, 'post', data={}, request_id=str(uuid4())).status_code in (401, 403)


def test_factories_build_orm_adapters():
    with patch.object(api, 'MinioMarkdownStore') as minio:
        documents = api._documents()
        assert documents.blobs is minio.return_value
        assert api._documents(blobs='custom').blobs == 'custom'
    assert isinstance(api._requests(), api.DjangoChangeRequestRepository)
