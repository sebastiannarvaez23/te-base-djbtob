"""Unit tests del módulo integration (sesión, captura, draft en error 500)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import patch

from django.test import RequestFactory, override_settings

from core.auth.cookies import ACCESS_ADMIN_COOKIE, ACCESS_CLIENT_COOKIE
from core.auth.jwt_service import create_access_token
from core.ui_context import UiContext, reset_ui_context, set_ui_context
from platform.features.support.incidents.incident import integration


class IntegrationSessionTests(TestCase):

    def setUp(self):
        self.rf = RequestFactory()

    def test_has_client_session_false_without_cookie(self):
        req = self.rf.get('/')
        self.assertFalse(integration.has_client_session(req))

    def test_has_client_session_true_with_cookie(self):
        req = self.rf.get('/')
        req.COOKIES[ACCESS_CLIENT_COOKIE] = 'tok'
        self.assertTrue(integration.has_client_session(req))

    def test_resolve_session_id_from_client_token(self):
        req = self.rf.get('/')
        token = create_access_token(
            user_id='u1', user_type='client',
            schema_name='arisoft', session_id='sid-abc',
        )
        req.COOKIES[ACCESS_CLIENT_COOKIE] = token
        self.assertEqual(integration.resolve_client_session_id(req), 'sid-abc')

    def test_resolve_session_id_none_for_admin_token(self):
        req = self.rf.get('/')
        token = create_access_token(user_id='a1', user_type='admin', schema_name='public')
        req.COOKIES[ACCESS_CLIENT_COOKIE] = token
        self.assertIsNone(integration.resolve_client_session_id(req))

    def test_resolve_session_id_none_for_invalid_token(self):
        req = self.rf.get('/')
        req.COOKIES[ACCESS_CLIENT_COOKIE] = 'not.valid.jwt'
        self.assertIsNone(integration.resolve_client_session_id(req))

    def test_has_incident_session_true_with_admin_cookie(self):
        req = self.rf.get('/')
        req.COOKIES[ACCESS_ADMIN_COOKIE] = 'tok'
        self.assertTrue(integration.has_incident_session(req))
        self.assertFalse(integration.has_client_session(req))

    def test_resolve_incident_session_id_from_admin_token(self):
        req = self.rf.get('/')
        token = create_access_token(
            user_id='a1', user_type='admin',
            schema_name='public', session_id='sid-admin',
        )
        req.COOKIES[ACCESS_ADMIN_COOKIE] = token
        self.assertEqual(integration.resolve_admin_session_id(req), 'sid-admin')
        self.assertEqual(integration.resolve_incident_session_id(req), 'sid-admin')


class BuildIncidentForErrorTests(TestCase):

    def setUp(self):
        self.rf = RequestFactory()
        reset_ui_context()

    def tearDown(self):
        reset_ui_context()

    def _client_request(self):
        req = self.rf.post('/api/v1/x/', data='{"a":1}', content_type='application/json')
        req.request_id = 'req-1'
        token = create_access_token(
            user_id='u1', user_type='client',
            schema_name='arisoft', session_id='sid-1',
        )
        req.COOKIES[ACCESS_CLIENT_COOKIE] = token
        return req

    @override_settings(INCIDENT_CAPTURE_ENABLED=False)
    def test_returns_none_when_capture_disabled(self):
        req = self._client_request()
        self.assertIsNone(integration.build_incident_for_error(req, error={'code': 'SRV_001'}))

    def test_returns_none_without_client_session(self):
        req = self.rf.post('/api/v1/x/')
        req.request_id = 'req-1'
        self.assertIsNone(integration.build_incident_for_error(req, error={'code': 'SRV_001'}))

    @patch('platform.features.support.incidents.incident.integration.CreateIncidentDraftUseCase')
    @override_settings(INCIDENT_CAPTURE_ENABLED=True)
    def test_includes_ui_context_in_failed_request(self, mock_uc_cls):
        set_ui_context(UiContext(
            module_id='mod-uuid',
            functionality_id='fn-uuid',
            page_section='profile',
            feature_key='settings.profile.edit',
        ))
        mock_uc_cls.return_value.execute.return_value = 'draft-tok'
        req = self._client_request()
        result = integration.build_incident_for_error(req, error={'code': 'SRV_001'})

        self.assertEqual(result['token'], 'draft-tok')
        self.assertIn('report_url', result)
        _, kwargs = mock_uc_cls.return_value.execute.call_args
        failed = kwargs['failed_request']
        self.assertEqual(failed['module_id'], 'mod-uuid')
        self.assertEqual(failed['functionality_id'], 'fn-uuid')
        self.assertEqual(failed['page_section'], 'profile')
        self.assertEqual(failed['feature_key'], 'settings.profile.edit')
        self.assertEqual(failed['request_id'], 'req-1')

    @patch('platform.features.support.incidents.incident.integration.CreateIncidentDraftUseCase')
    @override_settings(INCIDENT_CAPTURE_ENABLED=True)
    def test_build_incident_accepts_admin_session(self, mock_uc_cls):
        mock_uc_cls.return_value.execute.return_value = 'draft-admin'
        req = self.rf.post('/api/v1/platform/x/', data='{}', content_type='application/json')
        req.request_id = 'req-admin'
        token = create_access_token(
            user_id='a1', user_type='admin',
            schema_name='public', session_id='sid-admin',
        )
        req.COOKIES[ACCESS_ADMIN_COOKIE] = token
        result = integration.build_incident_for_error(req, error={'code': 'SRV_001'})
        self.assertEqual(result['token'], 'draft-admin')

    @patch('platform.features.support.incidents.incident.integration.CreateIncidentDraftUseCase')
    @override_settings(INCIDENT_CAPTURE_ENABLED=True)
    def test_freezes_synthetic_frontend_log_for_the_failed_request(self, mock_uc_cls):
        mock_uc_cls.return_value.execute.return_value = 'draft-tok'
        req = self._client_request()
        integration.build_incident_for_error(req, error={'code': 'SRV_001'})
        _, kwargs = mock_uc_cls.return_value.execute.call_args
        logs = kwargs['frontend_logs']
        self.assertTrue(logs)
        self.assertEqual(logs[-1]['level'], 'error')
        self.assertIn('POST /api/v1/x/ → 500 SRV_001', logs[-1]['message'])

    @patch('platform.features.support.incidents.incident.integration.CreateIncidentDraftUseCase')
    @override_settings(INCIDENT_CAPTURE_ENABLED=True)
    def test_reads_frontend_logs_header(self, mock_uc_cls):
        import base64
        import json

        mock_uc_cls.return_value.execute.return_value = 'draft-tok'
        payload = [{'t': '2026-08-29T12:00:00Z', 'l': 'e', 'm': 'console boom'}]
        encoded = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('ascii')
        req = self._client_request()
        req.META['HTTP_X_WA_FRONTEND_LOGS'] = encoded
        integration.build_incident_for_error(req, error={'code': 'SRV_001'})
        _, kwargs = mock_uc_cls.return_value.execute.call_args
        messages = [item['message'] for item in kwargs['frontend_logs']]
        self.assertIn('console boom', messages)
        self.assertTrue(any('→ 500 SRV_001' in msg for msg in messages))

    @patch('platform.features.support.incidents.incident.integration._run_capture')
    @override_settings(INCIDENT_CAPTURE_ENABLED=True, INCIDENT_CAPTURE_ASYNC=False)
    def test_capture_transaction_passes_ui_fields(self, mock_run):
        integration.capture_transaction(
            'sid',
            request_id='r1', ts='t', module_id='m1',
            functionality_id='f1', page_section='users',
            feature_key='orders.view',
        )
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        self.assertEqual(kwargs['module_id'], 'm1')
        self.assertEqual(kwargs['page_section'], 'users')
        self.assertEqual(kwargs['feature_key'], 'orders.view')

    @patch('platform.features.support.incidents.incident.integration.threading.Thread')
    @override_settings(INCIDENT_CAPTURE_ENABLED=True, INCIDENT_CAPTURE_ASYNC=True)
    def test_capture_async_spawns_thread(self, mock_thread):
        mock_thread.return_value.start = lambda: None
        integration.capture_transaction('sid', request_id='r', ts='t')
        mock_thread.assert_called_once()
        self.assertTrue(mock_thread.call_args[1]['daemon'])
