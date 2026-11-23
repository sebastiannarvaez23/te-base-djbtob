"""Chaos tests: con Redis caído, la captura y el reporte degradan en silencio
y el request nunca se rompe ni propaga excepciones."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import patch

from django.test import RequestFactory

from core.auth.cookies import ACCESS_CLIENT_COOKIE
from core.auth.jwt_service import create_access_token
from core.errors.handler import app_exception_handler
from platform.features.support.incidents.incident import integration
from platform.features.support.incidents.incident.infrastructure import redis_buffer, redis_draft_store

_DOWN = RuntimeError('Connection refused')


class RedisDownChaosTests(TestCase):

    def setUp(self):
        self.rf = RequestFactory()

    def _client_request(self):
        req = self.rf.post('/api/v1/x/', data='{"a":1}', content_type='application/json')
        req.request_id = 'req-chaos'
        token = create_access_token(user_id='u1', user_type='client',
                                    schema_name='arisoft', session_id='sid-chaos')
        req.COOKIES[ACCESS_CLIENT_COOKIE] = token
        return req

    def test_capture_transaction_survives_redis_down(self):
        with patch.object(redis_buffer, '_get_client', side_effect=_DOWN):
            # No debe lanzar
            integration.capture_transaction(
                'sid', request_id='r', ts='t', logs=['a'])

    def test_build_incident_for_error_survives_redis_down(self):
        req = self._client_request()
        with patch.object(redis_buffer, '_get_client', side_effect=_DOWN), \
             patch.object(redis_draft_store, '_get_client', side_effect=_DOWN):
            # No propaga; devuelve el bloque o None, pero nunca revienta.
            result = integration.build_incident_for_error(
                req, error={'code': 'SRV_001', 'http_status': 500})
        self.assertTrue(result is None or 'report_url' in result)

    def test_exception_handler_returns_500_even_if_incident_build_raises(self):
        req = self._client_request()
        ctx = {'request': req, 'view': None}
        with patch(
            'platform.features.support.incidents.incident.integration.build_incident_for_error',
            side_effect=_DOWN,
        ):
            resp = app_exception_handler(Exception('boom'), ctx)
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn('incident', resp.data['error'])

    def test_chaos_ui_context_header_survives_redis_down(self):
        from core.ui_context import parse_ui_context_header, reset_ui_context, set_ui_context

        ctx = parse_ui_context_header(
            'fk=orders.view;ps=list;mid=a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'
        )
        set_ui_context(ctx)
        try:
            with patch.object(redis_buffer, '_get_client', side_effect=_DOWN), \
                 patch.object(redis_draft_store, '_get_client', side_effect=_DOWN):
                integration.capture_transaction('sid', request_id='r', ts='t')
                req = self._client_request()
                req.META['HTTP_X_UI_CONTEXT'] = 'fk=orders.view;ps=list'
                result = integration.build_incident_for_error(req, error={'code': 'SRV_001'})
        finally:
            reset_ui_context()
        self.assertTrue(result is None or 'token' in (result or {}))
