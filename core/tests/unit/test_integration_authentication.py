"""Unit tests — IntegrationBearerAuthentication + HasIntegrationScope."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response

from core.auth.integration.authentication import IntegrationBearerAuthentication
from core.auth.integration.jwt_service import create_integration_access_token
from core.auth.integration.permissions import HasIntegrationScope, IntegrationPlanAccess
from core.auth.integration.principal import IntegrationPrincipal
from core.auth.integration.views import IntegrationAPIView
from core.errors import AppErrorCode, AuthException, SubscriptionException
from core.errors.exceptions import PermissionException


def _request(auth_header: str | None = None):
    meta = {}
    if auth_header:
        meta['HTTP_AUTHORIZATION'] = auth_header
    return SimpleNamespace(META=meta)


@pytest.mark.unit
class TestIntegrationBearerAuthentication:

    def test_missing_header_returns_none(self):
        assert IntegrationBearerAuthentication().authenticate(_request()) is None

    def test_non_bearer_returns_none(self):
        assert IntegrationBearerAuthentication().authenticate(
            _request('Basic abc'),
        ) is None

    def test_valid_token_returns_principal(self):
        with override_settings(INTEGRATION_JWT_SECRET='int-secret'):
            token, _ = create_integration_access_token(
                app_id='11111111-1111-1111-1111-111111111111',
                client_id='wa_test',
                schema_name='tenant_a',
                scopes=['orders:read'],
            )
            app = SimpleNamespace(
                id='11111111-1111-1111-1111-111111111111',
                client_id='wa_test',
                name='Test App',
                status='ACTIVE',
            )
            with patch.object(
                IntegrationBearerAuthentication, '_load_active_app', return_value=app,
            ), patch(
                'django.db.connection',
                new=SimpleNamespace(schema_name='tenant_a'),
            ):
                user, payload = IntegrationBearerAuthentication().authenticate(
                    _request(f'Bearer {token}'),
                )
        assert isinstance(user, IntegrationPrincipal)
        assert user.client_id == 'wa_test'
        assert user.has_scope('orders:read')
        assert payload['user_type'] == 'integration'

    def test_inactive_app_raises(self):
        with override_settings(INTEGRATION_JWT_SECRET='int-secret'):
            token, _ = create_integration_access_token(
                app_id='11111111-1111-1111-1111-111111111111',
                client_id='wa_test',
                schema_name='tenant_a',
                scopes=[],
            )
            with patch.object(
                IntegrationBearerAuthentication, '_load_active_app', return_value=None,
            ):
                with pytest.raises(AuthenticationFailed, match='inactive'):
                    IntegrationBearerAuthentication().authenticate(
                        _request(f'Bearer {token}'),
                    )

    def test_tenant_mismatch_raises(self):
        with override_settings(INTEGRATION_JWT_SECRET='int-secret'):
            token, _ = create_integration_access_token(
                app_id='11111111-1111-1111-1111-111111111111',
                client_id='wa_test',
                schema_name='tenant_a',
                scopes=[],
            )
            app = SimpleNamespace(
                id='11111111-1111-1111-1111-111111111111',
                client_id='wa_test',
                name='T',
                status='ACTIVE',
            )
            with patch.object(
                IntegrationBearerAuthentication, '_load_active_app', return_value=app,
            ), patch(
                'django.db.connection',
                new=SimpleNamespace(schema_name='tenant_other'),
            ):
                with pytest.raises(AuthenticationFailed, match='mismatch'):
                    IntegrationBearerAuthentication().authenticate(
                        _request(f'Bearer {token}'),
                    )

    def test_invalid_token_raises(self):
        with override_settings(INTEGRATION_JWT_SECRET='int-secret'):
            with pytest.raises(AuthenticationFailed):
                IntegrationBearerAuthentication().authenticate(
                    _request('Bearer not-a-jwt'),
                )


@pytest.mark.unit
class TestHasIntegrationScope:

    def test_requires_principal(self):
        perm = HasIntegrationScope()
        view = SimpleNamespace(required_scopes=['orders:write'])
        request = SimpleNamespace(user=MagicMock())
        assert perm.has_permission(request, view) is False

    def test_allows_when_scopes_present(self):
        perm = HasIntegrationScope()
        view = SimpleNamespace(required_scopes=['orders:read'])
        request = SimpleNamespace(
            user=IntegrationPrincipal(
                app_id='a', client_id='c', schema_name='t',
                scopes=['orders:read', 'orders:write'],
            ),
        )
        assert perm.has_permission(request, view) is True

    def test_missing_scope_raises_scope_denied(self):
        perm = HasIntegrationScope()
        view = SimpleNamespace(required_scopes=['orders:write', 'orders:read'])
        request = SimpleNamespace(
            user=IntegrationPrincipal(
                app_id='a', client_id='c', schema_name='t',
                scopes=['orders:read'],
            ),
        )
        with pytest.raises(AuthException) as exc:
            perm.has_permission(request, view)
        assert exc.value.code == AppErrorCode.AUTH_SCOPE_DENIED
        assert 'orders:write' in exc.value.detail

    def test_no_required_scopes_allows_any_principal(self):
        perm = HasIntegrationScope()
        view = SimpleNamespace()
        request = SimpleNamespace(
            user=IntegrationPrincipal(
                app_id='a', client_id='c', schema_name='t', scopes=[],
            ),
        )
        assert perm.has_permission(request, view) is True


CHECKER = 'core.access.checker.AccessChecker.ensure_access_or_raise'


def _plan_request(schema_name='tenant_a', tenant_schema='tenant_a'):
    tenant = None if tenant_schema is None else SimpleNamespace(id='c1', schema_name=tenant_schema)
    return SimpleNamespace(
        user=IntegrationPrincipal(
            app_id='a', client_id='c', schema_name=schema_name, scopes=['x.api.list'],
        ),
        tenant=tenant,
    )


@pytest.mark.unit
class TestIntegrationPlanAccess:

    def test_requires_principal(self):
        request = SimpleNamespace(user=MagicMock(), tenant=None)
        assert IntegrationPlanAccess().has_permission(request, SimpleNamespace()) is False

    def test_checks_every_required_scope_without_quota(self):
        request = _plan_request()
        view = SimpleNamespace(required_scopes=('x.api.list', 'y.api.list'))
        with patch(CHECKER) as ensure:
            assert IntegrationPlanAccess().has_permission(request, view) is True
        assert [c.args[1] for c in ensure.call_args_list] == ['x.api.list', 'y.api.list']
        assert all(c.kwargs == {'check_quota': False} for c in ensure.call_args_list)
        assert ensure.call_args_list[0].args[0] is request.tenant

    @pytest.mark.parametrize('tenant_schema', [None, 'public', 'tenant_b'])
    def test_token_of_another_tenant_is_rejected(self, tenant_schema):
        request = _plan_request(tenant_schema=tenant_schema)
        with patch(CHECKER) as ensure, pytest.raises(AuthException) as exc:
            IntegrationPlanAccess().has_permission(request, SimpleNamespace(required_scopes=('x.api.list',)))
        assert exc.value.code == AppErrorCode.AUTH_TOKEN_INVALID
        ensure.assert_not_called()

    @pytest.mark.parametrize('exc_cls,code', [
        (SubscriptionException, AppErrorCode.SUB_NO_ACTIVE),
        (SubscriptionException, AppErrorCode.SUB_FEATURE_DENIED),
        (PermissionException, AppErrorCode.MODULE_INACTIVE),
    ])
    def test_plan_or_catalog_denial_propagates(self, exc_cls, code):
        request = _plan_request()
        with patch(CHECKER, side_effect=exc_cls(code)), pytest.raises(exc_cls) as exc:
            IntegrationPlanAccess().has_permission(request, SimpleNamespace(required_scopes=('x.api.list',)))
        assert exc.value.code == code


@pytest.mark.unit
class TestIntegrationAPIView:

    def test_view_without_required_scopes_is_misconfigured(self):
        class NoScopeView(IntegrationAPIView):
            def get(self, request):
                return Response({})

        with pytest.raises(ImproperlyConfigured):
            NoScopeView.as_view()

    def test_only_integration_bearer_authenticates(self):
        assert IntegrationAPIView.authentication_classes == [IntegrationBearerAuthentication]
        assert IntegrationAPIView.permission_classes == [HasIntegrationScope, IntegrationPlanAccess]
