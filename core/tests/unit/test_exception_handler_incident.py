"""Tests del exception handler: el bloque `incident` (token + URL) solo aparece
en errores ≥500, y el `trace_id` se alinea con `request.request_id`.
"""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import patch

from django.test import RequestFactory
from rest_framework.exceptions import NotAuthenticated

import pytest

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ServerException, ValidationAppException
from core.errors.handler import app_exception_handler

pytestmark = pytest.mark.unit

_INCIDENT = {'token': 'tok-123', 'report_url': '/api/v1/incidents/report/'}


class ExceptionHandlerIncidentTests(TestCase):

    def setUp(self):
        self.rf = RequestFactory()
        self.request = self.rf.post('/api/v1/things/')
        self.request.request_id = 'req-xyz'
        self.ctx = {'request': self.request, 'view': None}
        # Neutraliza la creación real del draft (Redis/JWT).
        self.patcher = patch(
            'platform.features.support.incidents.incident.integration.build_incident_for_error',
            return_value=_INCIDENT,
        )
        self.build_mock = self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _error_block(self, exc):
        return app_exception_handler(exc, self.ctx).data['error']

    def test_unhandled_500_includes_incident(self):
        block = self._error_block(Exception('boom'))
        self.assertEqual(block['incident'], _INCIDENT)

    def test_app_exception_5xx_includes_incident(self):
        block = self._error_block(ServerException(AppErrorCode.SERVER_ERROR))
        self.assertEqual(block['incident'], _INCIDENT)

    def test_business_4xx_has_no_incident(self):
        block = self._error_block(ValidationAppException(AppErrorCode.VALIDATION_ERROR))
        self.assertNotIn('incident', block)
        self.build_mock.assert_not_called()

    def test_http404_has_no_incident(self):
        from django.http import Http404

        block = self._error_block(Http404())
        self.assertNotIn('incident', block)
        self.build_mock.assert_not_called()

    def test_auth_401_has_no_incident(self):
        block = self._error_block(NotAuthenticated())
        self.assertNotIn('incident', block)

    def test_not_authenticated_uses_english_registry_copy(self):
        response = app_exception_handler(NotAuthenticated(), self.ctx)
        self.assertEqual(response.data['message'], 'Invalid token')
        self.assertEqual(
            response.data['detail'],
            'The authentication token is invalid or has expired.',
        )

    def test_authentication_failed_uses_english_registry_copy(self):
        from django.utils import translation
        from rest_framework.exceptions import AuthenticationFailed

        with translation.override('es'):
            response = app_exception_handler(AuthenticationFailed(), self.ctx)
        self.assertEqual(response.data['message'], 'Invalid token')
        self.assertEqual(
            response.data['detail'],
            'The authentication token is invalid or has expired.',
        )

    def test_trace_id_aligned_with_request_id(self):
        block = self._error_block(Exception('boom'))
        self.assertEqual(block['trace_id'], 'req-xyz')

    @patch('core.ui_context.ui_context_dict', return_value={
        'module_id': 'mod-1',
        'functionality_id': 'fn-1',
        'page_section': 'profile',
    })
    def test_incident_build_receives_ui_context(self, _mock_ctx):
        self._error_block(Exception('boom'))
        _, kwargs = self.build_mock.call_args
        ui = kwargs['error']['ui_context']
        self.assertEqual(ui['module_id'], 'mod-1')
        self.assertEqual(ui['page_section'], 'profile')
