"""Unit tests for CatalogStatusCache and CatalogAccessMiddleware."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.http import JsonResponse
from django.test import RequestFactory

from core.access.catalog_cache import CatalogStatusCache
from core.access.catalog_middleware import CatalogAccessMiddleware
from core.access.result import AccessResult
from core.errors import AppErrorCode

pytestmark = pytest.mark.unit


def _snapshot(**overrides):
    base = {
        'epoch': 1,
        'by_code': {
            'DASHBOARD': {
                'id': '11111111-1111-1111-1111-111111111111',
                'is_active': True,
                'section_code': 'WMS',
                'section_active': True,
            },
            'ORDERS': {
                'id': '22222222-2222-2222-2222-222222222222',
                'is_active': False,
                'section_code': 'WMS',
                'section_active': True,
            },
            'PICKING': {
                'id': '33333333-3333-3333-3333-333333333333',
                'is_active': True,
                'section_code': 'WMS',
                'section_active': False,
            },
        },
        'by_id': {
            '11111111-1111-1111-1111-111111111111': 'DASHBOARD',
            '22222222-2222-2222-2222-222222222222': 'ORDERS',
            '33333333-3333-3333-3333-333333333333': 'PICKING',
        },
        'by_api_prefix': {
            'warehouse/home': 'DASHBOARD',
            'warehouse/orders': 'ORDERS',
            'warehouse/picking': 'PICKING',
        },
    }
    base.update(overrides)
    return base


class TestCatalogStatusCache:
    @patch.object(CatalogStatusCache, 'get_or_load', return_value=_snapshot())
    def test_inactive_module(self, _mock):
        result = CatalogStatusCache.check_module_code('ORDERS')
        assert result.error_code == AppErrorCode.MODULE_INACTIVE

    @patch.object(CatalogStatusCache, 'get_or_load', return_value=_snapshot())
    def test_inactive_section_wins(self, _mock):
        result = CatalogStatusCache.check_module_code('PICKING')
        assert result.error_code == AppErrorCode.SECTION_INACTIVE

    @patch.object(CatalogStatusCache, 'get_or_load', return_value=_snapshot())
    def test_active_allowed(self, _mock):
        assert CatalogStatusCache.check_module_code('DASHBOARD').is_allowed

    @patch.object(CatalogStatusCache, 'get_or_load', return_value=_snapshot())
    def test_resolve_api_path(self, _mock):
        code = CatalogStatusCache.resolve_code_from_api_path(
            '/api/v1/warehouse/orders/123/'
        )
        assert code == 'ORDERS'

    @pytest.mark.parametrize('path', [
        '/api/v1/warehouse/receiving/',
        '/api/v1/warehouse/inventory/',
        '/api/v1/warehouse/facilities/zones/',
        '/api/v1/third-parties/',
    ])
    @patch.object(CatalogStatusCache, 'get_or_load')
    def test_removed_product_paths_do_not_map(self, mock_load, path):
        snap = _snapshot()
        for code in ('RECEPTION', 'INVENTORIES', 'WAREHOUSE', 'THIRD_PARTIES'):
            snap['by_code'][code] = {
                'id': '44444444-4444-4444-4444-444444444444',
                'is_active': True,
                'section_code': 'OPERATIONAL',
                'section_active': True,
            }
        mock_load.return_value = snap
        assert CatalogStatusCache.resolve_code_from_api_path(path) == ''

    @pytest.mark.parametrize('path, code', [
        ('/api/v1/company-users/', 'USERS_ROLES'),
        ('/api/v1/integrations/connections/', 'INTEGRATIONS'),
        ('/api/v1/assistant/', 'WA_ASSISTANT'),
    ])
    @patch.object(CatalogStatusCache, 'get_or_load')
    def test_shell_api_maps_to_module(self, mock_load, path, code):
        snap = _snapshot()
        snap['by_code'][code] = {
            'id': '44444444-4444-4444-4444-444444444444',
            'is_active': True,
            'section_code': 'SETTINGS',
            'section_active': True,
        }
        mock_load.return_value = snap
        assert CatalogStatusCache.resolve_code_from_api_path(path) == code

    @patch.object(CatalogStatusCache, 'get_or_load', return_value=_snapshot())
    def test_unknown_module_id_is_denied(self, _mock):
        result = CatalogStatusCache.check_module_id('99999999-9999-9999-9999-999999999999')
        assert result.error_code == AppErrorCode.MODULE_INACTIVE

    @patch.object(CatalogStatusCache, 'set_snapshot')
    @patch('platform.features.security.access.modules.models.Module')
    def test_failed_load_is_not_cached_and_denies(self, MockModule, mock_set):
        MockModule.objects.select_related.side_effect = RuntimeError('db down')
        snap = CatalogStatusCache.load_snapshot()
        assert snap['ok'] is False
        mock_set.assert_not_called()

        with patch.object(CatalogStatusCache, 'get_or_load', return_value=snap):
            result = CatalogStatusCache.check_module_code('ORDERS')
        assert result.error_code == AppErrorCode.MODULE_INACTIVE


class TestCatalogAccessMiddleware:
    def setup_method(self):
        self.factory = RequestFactory()
        self.mw = CatalogAccessMiddleware(get_response=lambda r: JsonResponse({'ok': True}))

    def _authed(self, path, **headers):
        request = self.factory.get(path, **headers)
        request.subscription_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        request.access_mode = 'full'
        return request

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'check_module_code')
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='')
    def test_denies_inactive_module_from_header(self, _path, mock_check, _client):
        mock_check.return_value = AccessResult.module_inactive(module_code='DASHBOARD')
        request = self._authed(
            '/api/v1/warehouse/home/pulse/',
            HTTP_X_UI_CONTEXT='mc=DASHBOARD',
        )
        response = self.mw(request)
        assert response.status_code == 403
        body = response.content.decode()
        assert 'MOD_004' in body

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'check_module_code')
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='ORDERS')
    def test_active_header_cannot_bypass_inactive_api(self, _path, mock_check, _client):
        """mc de un módulo activo no oculta la API de un módulo inactivo."""
        def _check(code):
            if code == 'ORDERS':
                return AccessResult.module_inactive(module_code='ORDERS')
            return AccessResult.allowed()

        mock_check.side_effect = _check
        request = self._authed(
            '/api/v1/warehouse/orders/',
            HTTP_X_UI_CONTEXT='mc=DASHBOARD',
        )
        response = self.mw(request)
        assert response.status_code == 403
        assert b'MOD_004' in response.content
        assert mock_check.call_args_list[0].args[0] == 'ORDERS'

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'check_module_code')
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='ORDERS')
    def test_denies_from_api_path(self, _path, mock_check, _client):
        mock_check.return_value = AccessResult.module_inactive(module_code='ORDERS')
        request = self._authed('/api/v1/warehouse/orders/')
        response = self.mw(request)
        assert response.status_code == 403
        assert b'MOD_004' in response.content

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'check_module_code')
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='DASHBOARD')
    def test_allows_active_module(self, _path, mock_check, _client):
        mock_check.return_value = AccessResult.allowed()
        request = self._authed(
            '/api/v1/warehouse/home/pulse/',
            HTTP_X_UI_CONTEXT='mc=DASHBOARD',
        )
        response = self.mw(request)
        assert response.status_code == 200

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    def test_skips_auth_paths_for_catalog_when_subscribed(self, _client):
        request = self._authed('/api/v1/auth/me/', HTTP_X_UI_CONTEXT='mc=DASHBOARD')
        response = self.mw(request)
        assert response.status_code == 200

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    def test_denies_warehouse_without_subscription(self, _client):
        request = self.factory.get(
            '/api/v1/warehouse/orders/',
            HTTP_X_UI_CONTEXT='mc=ORDERS',
        )
        request.subscription_id = None
        request.access_mode = 'full'
        response = self.mw(request)
        assert response.status_code == 403
        assert b'SUB_001' in response.content

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    def test_denies_auth_me_without_subscription(self, _client):
        """auth/me no está exento del gate SUB_001 (corta sesión en caliente)."""
        request = self.factory.get('/api/v1/auth/me/')
        request.subscription_id = ''
        request.access_mode = 'full'
        response = self.mw(request)
        assert response.status_code == 403
        assert b'SUB_001' in response.content

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    def test_allows_logout_without_subscription(self, _client):
        request = self.factory.get('/api/v1/auth/logout/')
        request.subscription_id = None
        response = self.mw(request)
        assert response.status_code == 200

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    def test_skips_sub_gate_in_billing_recovery(self, _client):
        request = self.factory.get('/api/v1/warehouse/orders/')
        request.subscription_id = None
        request.access_mode = 'billing_recovery'
        response = self.mw(request)
        assert response.status_code == 200

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='')
    def test_unmapped_bound_api_is_denied(self, _path, _client):
        request = self._authed(
            '/api/v1/integrations/not-a-module/',
            HTTP_X_UI_CONTEXT='mc=DASHBOARD',
        )
        response = self.mw(request)
        assert response.status_code == 403
        assert b'MOD_004' in response.content

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'check_module_code', return_value=AccessResult.allowed())
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='')
    def test_record_trace_follows_active_header_module(self, _path, mock_check, _client):
        request = self._authed(
            '/api/v1/record-trace/?reference_id=01a0e113-0ed6-7245-8407-f11befaa6763',
            HTTP_X_UI_CONTEXT='mc=WAREHOUSE',
        )
        response = self.mw(request)
        assert response.status_code == 200
        mock_check.assert_called_once_with('WAREHOUSE')

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'check_module_code')
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='')
    def test_record_trace_denied_when_header_module_inactive(self, _path, mock_check, _client):
        mock_check.return_value = AccessResult.module_inactive(module_code='WAREHOUSE')
        request = self._authed('/api/v1/record-trace/', HTTP_X_UI_CONTEXT='mc=WAREHOUSE')
        response = self.mw(request)
        assert response.status_code == 403
        assert b'MOD_004' in response.content

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'check_module_code', return_value=AccessResult.allowed())
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='')
    def test_attention_follows_active_header_module(self, _path, mock_check, _client):
        request = self._authed('/api/v1/attention/?module=orders', HTTP_X_UI_CONTEXT='mc=ORDERS')
        response = self.mw(request)
        assert response.status_code == 200
        mock_check.assert_called_once_with('ORDERS')

    @patch.object(CatalogAccessMiddleware, '_is_client_api', return_value=True)
    @patch.object(CatalogStatusCache, 'resolve_code_from_api_path', return_value='')
    def test_inbox_without_module_stays_open_when_subscribed(self, _path, _client):
        request = self._authed('/api/v1/client/inbox/unread-count/')
        response = self.mw(request)
        assert response.status_code == 200

    def test_admin_auth_context_skips_client_gates(self):
        """Admin PATCH con cookie client residual no debe recibir SUB_001."""
        request = self.factory.patch(
            '/api/v1/billing/subscriptions/a5a4fc1d-4f9e-4058-a6aa-8181fc5b970b/',
            data='{"is_active":false}',
            content_type='application/json',
            HTTP_X_AUTH_CONTEXT='admin',
        )
        request.COOKIES = {'access_client': 'fake-client-jwt'}
        request.subscription_id = None
        response = self.mw(request)
        assert response.status_code == 200
