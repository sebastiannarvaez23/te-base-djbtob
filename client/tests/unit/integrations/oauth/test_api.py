"""Unit tests — Integration Application HTTP views (no DB).

The ORM repository and credential factory are swapped for in-memory fakes
at the view module; audit/security logs and ``IsCompanyMember`` are patched.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from client.features.integrations.oauth.client.presentation import api
from client.tests.unit.integrations.oauth.conftest import (
    FakeCredentialFactory,
    FakeScopeCatalog,
    InMemoryIntegrationApplicationRepository,
)

API = 'client.features.integrations.oauth.client.presentation.api'
LOCMEM_CACHES = {
    name: {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': f'{name}-oauth-api'}
    for name in ('default', 'access', 'auth')
}
USER_ID = uuid.uuid4()


@pytest.fixture
def env():
    repo = InMemoryIntegrationApplicationRepository()
    creds = FakeCredentialFactory()
    catalog = FakeScopeCatalog()
    with override_settings(CACHES=LOCMEM_CACHES, INTEGRATION_JWT_SECRET='int-secret'), \
            patch(f'{API}._repo', return_value=repo), \
            patch(f'{API}._credentials', return_value=creds), \
            patch(f'{API}._actor_scopes', return_value=catalog), \
            patch(f'{API}._tenant_scopes', return_value=catalog), \
            patch(f'{API}.audit_log') as audit, \
            patch(f'{API}.security_log') as security, \
            patch(f'{API}.IsCompanyMember.has_permission', return_value=True):
        yield SimpleNamespace(repo=repo, audit=audit, security=security, catalog=catalog)


def _call(view_cls, method, path='/oauth/apps/', data=None, authenticated=True, **kwargs):
    factory = APIRequestFactory()
    request = getattr(factory, method)(path, data, format='json')
    if authenticated:
        force_authenticate(request, user=SimpleNamespace(id=USER_ID, pk=USER_ID, is_authenticated=True))
    return view_cls.as_view()(request, **kwargs)


def _create(name='ERP bridge', scopes=None):
    return _call(
        api.IntegrationApplicationListCreateView, 'post',
        data={'name': name, 'scopes': scopes or ['api.orders.read']},
    )


def _app_id(response) -> uuid.UUID:
    return uuid.UUID(response.data['data']['application']['id'])


@pytest.mark.unit
class TestListCreate:

    def test_create_returns_201_with_secret_and_audits(self, env):
        response = _create()
        assert response.status_code == 201
        assert response.data['message'] == 'Integration application created.'
        data = response.data['data']
        assert data['client_secret']
        assert data['application']['status'] == 'ACTIVE'
        assert data['application']['created_by'] == str(USER_ID)
        env.audit.assert_called_once()
        assert data['client_secret'] not in str(env.audit.call_args)

    def test_create_invalid_body_is_400(self, env):
        response = _call(api.IntegrationApplicationListCreateView, 'post', data={'name': 'A'})
        assert response.status_code == 400
        fields = {e['field'] for e in response.data['errors']}
        assert {'name', 'scopes'} <= fields
        assert env.repo.writes == 0

    def test_requires_authentication(self, env):
        response = _call(api.IntegrationApplicationListCreateView, 'get', authenticated=False)
        assert response.status_code in (401, 403)

    def test_list_paginated(self, env):
        _create('A app')
        _create('B app')
        response = _call(api.IntegrationApplicationListCreateView, 'get', path='/oauth/apps/?page=1&page_size=1')
        assert response.status_code == 200
        payload = response.data['data']
        assert payload['total'] == 2
        assert len(payload['items']) == 1

    def test_list_rejects_unknown_status_filter(self, env):
        response = _call(api.IntegrationApplicationListCreateView, 'get', path='/oauth/apps/?status=GONE')
        assert response.status_code == 400

    def test_create_with_scope_outside_role_is_403(self, env):
        env.catalog.grantable = ['api.orders.read']
        response = _create(scopes=['api.orders.write'])
        assert response.status_code == 403
        assert response.data['error']['code'] == 'INT_015'
        assert env.repo.writes == 0

    def test_create_with_non_api_functionality_is_400(self, env):
        response = _create(scopes=['api.orders.read', 'orders.view'])
        assert response.status_code == 400
        assert response.data['error']['code'] == 'INT_016'
        assert env.repo.writes == 0

    def test_create_rejects_malformed_scope(self, env):
        response = _create(scopes=['Orders Read!'])
        assert response.status_code == 400
        assert response.data['errors'][0]['field'] == 'scopes[0]'


@pytest.mark.unit
class TestScopes:

    def test_lists_grantable_scopes(self, env):
        env.catalog.grantable = ['api.orders.read', 'api.inventories.read']
        response = _call(api.IntegrationScopeListView, 'get', path='/oauth/scopes/')
        assert response.status_code == 200
        assert [s['key'] for s in response.data['data']] == ['api.orders.read', 'api.inventories.read']
        assert set(response.data['data'][0]) == {'key', 'label', 'module', 'module_name'}

    def test_requires_authentication(self, env):
        response = _call(api.IntegrationScopeListView, 'get', path='/oauth/scopes/', authenticated=False)
        assert response.status_code in (401, 403)


@pytest.mark.unit
class TestDetail:

    def test_get(self, env):
        app_id = _app_id(_create())
        response = _call(api.IntegrationApplicationDetailView, 'get', pk=app_id)
        assert response.status_code == 200
        assert response.data['data']['id'] == str(app_id)

    def test_get_missing_is_404(self, env):
        response = _call(api.IntegrationApplicationDetailView, 'get', pk=uuid.uuid4())
        assert response.status_code == 404
        assert response.data['error']['code'] == 'INT_010'

    def test_patch(self, env):
        app_id = _app_id(_create())
        response = _call(
            api.IntegrationApplicationDetailView, 'patch',
            data={'name': 'Renamed', 'scopes': ['api.inventories.read']}, pk=app_id,
        )
        assert response.status_code == 200
        assert response.data['message'] == 'Integration application updated.'
        assert response.data['data']['scopes'] == ['api.inventories.read']
        assert env.audit.call_args.kwargs['changes'] == {'name': 'Renamed', 'scopes': ['api.inventories.read']}

    def test_patch_status_rejected(self, env):
        app_id = _app_id(_create())
        response = _call(api.IntegrationApplicationDetailView, 'patch', data={'status': 'ACTIVE'}, pk=app_id)
        assert response.status_code == 400
        assert response.data['errors'][0]['code'] == 'UNKNOWN_FIELD'

    def test_delete_requires_revoke_then_succeeds(self, env):
        app_id = _app_id(_create())
        conflict = _call(api.IntegrationApplicationDetailView, 'delete', pk=app_id)
        assert conflict.status_code == 409
        assert conflict.data['error']['code'] == 'INT_013'

        _call(api.IntegrationApplicationRevokeView, 'post', pk=app_id)
        response = _call(api.IntegrationApplicationDetailView, 'delete', pk=app_id)
        assert response.status_code == 200
        assert response.data['message'] == 'Integration application deleted.'
        assert env.repo.get_by_id(app_id) is None


@pytest.mark.unit
class TestLifecycleEndpoints:

    def test_disable_enable_revoke_flow(self, env):
        app_id = _app_id(_create())

        disabled = _call(api.IntegrationApplicationDisableView, 'post', pk=app_id)
        assert disabled.status_code == 200
        assert disabled.data['data']['status'] == 'DISABLED'
        assert disabled.data['message'] == 'Integration application disabled.'

        enabled = _call(api.IntegrationApplicationEnableView, 'post', pk=app_id)
        assert enabled.data['data']['status'] == 'ACTIVE'

        revoked = _call(api.IntegrationApplicationRevokeView, 'post', pk=app_id)
        assert revoked.data['data']['status'] == 'REVOKED'
        assert revoked.data['message'] == 'Integration application revoked.'

        events = [c.kwargs['event_type'] for c in env.security.call_args_list]
        assert events == [
            'integration_oauth_app_disabled',
            'integration_oauth_app_enabled',
            'integration_oauth_app_revoked',
        ]

    def test_enable_revoked_is_409(self, env):
        app_id = _app_id(_create())
        _call(api.IntegrationApplicationRevokeView, 'post', pk=app_id)
        response = _call(api.IntegrationApplicationEnableView, 'post', pk=app_id)
        assert response.status_code == 409
        assert response.data['error']['code'] == 'INT_012'

    def test_rotate_secret(self, env):
        created = _create()
        app_id = _app_id(created)
        response = _call(api.IntegrationApplicationRotateSecretView, 'post', pk=app_id)
        assert response.status_code == 200
        assert response.data['message'] == 'Client secret rotated.'
        assert response.data['data']['client_secret'] != created.data['data']['client_secret']

    def test_rotate_missing_is_404(self, env):
        response = _call(api.IntegrationApplicationRotateSecretView, 'post', pk=uuid.uuid4())
        assert response.status_code == 404


@pytest.mark.unit
class TestTokenEndpoint:

    def test_issue_token(self, env):
        created = _create().data['data']
        with patch('client.features.integrations.oauth.client.application.use_cases.connection') as conn:
            conn.schema_name = 'tenant_acme'
            response = _call(
                api.OAuthTokenAPIView, 'post', path='/oauth/token/', authenticated=False,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': created['application']['client_id'],
                    'client_secret': created['client_secret'],
                },
            )
        assert response.status_code == 200
        assert response.data['message'] == 'Access token issued.'
        assert response.data['data']['token_type'] == 'Bearer'

    def test_bad_secret_is_401(self, env):
        created = _create().data['data']
        response = _call(
            api.OAuthTokenAPIView, 'post', path='/oauth/token/', authenticated=False,
            data={
                'grant_type': 'client_credentials',
                'client_id': created['application']['client_id'],
                'client_secret': 'wrong-secret-value-0000',
            },
        )
        assert response.status_code == 401
        env.security.assert_called_once()
        kwargs = env.security.call_args.kwargs
        assert kwargs['event_type'] == 'integration_oauth_token_denied'
        assert created['application']['client_id'] in kwargs['detail']
        assert 'wrong-secret-value-0000' not in kwargs['detail']

    def test_issue_token_security_logs_success(self, env):
        created = _create().data['data']
        with patch('client.features.integrations.oauth.client.application.use_cases.connection') as conn:
            conn.schema_name = 'tenant_acme'
            _call(
                api.OAuthTokenAPIView, 'post', path='/oauth/token/', authenticated=False,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': created['application']['client_id'],
                    'client_secret': created['client_secret'],
                },
            )
        assert env.security.call_args.kwargs['event_type'] == 'integration_oauth_token_issued'


@pytest.mark.unit
class TestListUnpaginated:

    def test_list_unpaginated_returns_plain_items(self, env):
        _create('A app')
        response = _call(api.IntegrationApplicationListCreateView, 'get', path='/oauth/apps/')
        assert response.status_code == 200
        assert [a['name'] for a in response.data['data']] == ['A app']


@pytest.mark.unit
class TestFactories:

    def test_adapters_are_concrete_implementations(self):
        from client.features.integrations.oauth.client.infrastructure import (
            AccessControlScopeCatalog,
            DjangoIntegrationApplicationRepository,
            SecureCredentialFactory,
        )
        company, user = object(), SimpleNamespace(pk=USER_ID)
        request = SimpleNamespace(user=user, tenant=company)
        assert isinstance(api._repo(), DjangoIntegrationApplicationRepository)
        assert isinstance(api._credentials(), SecureCredentialFactory)
        with patch(f'{API}.company_for_request', return_value=company):
            actor = api._actor_scopes(request)
        assert isinstance(actor, AccessControlScopeCatalog)
        assert isinstance(api._tenant_scopes(request), AccessControlScopeCatalog)

    @pytest.mark.parametrize('raw, expected', [
        (USER_ID, USER_ID),
        (str(USER_ID), USER_ID),
        (None, None),
        ('', None),
        ('not-a-uuid', None),
    ])
    def test_actor_id(self, raw, expected):
        assert api._actor_id(SimpleNamespace(user=SimpleNamespace(id=raw))) == expected


@pytest.mark.unit
def test_urls_resolve_to_views():
    from django.urls import resolve

    from client.features.integrations.oauth.client.presentation import urls

    def view_at(path):
        return resolve(path, urlconf=urls).func.view_class

    assert view_at('/scopes/') is api.IntegrationScopeListView
    assert view_at('/token/') is api.OAuthTokenAPIView
    assert view_at(f'/apps/{USER_ID}/rotate-secret/') is api.IntegrationApplicationRotateSecretView
