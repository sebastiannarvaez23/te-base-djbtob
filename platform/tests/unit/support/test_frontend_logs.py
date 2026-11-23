"""Unit tests for frontend log sanitization attached to incidents."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

from platform.features.support.incidents.incident.application.frontend_logs import (
    FRONTEND_LOG_LIMIT,
    sanitize_frontend_logs,
)
from platform.features.support.incidents.incident.presentation.bodies import (
    ReportIncidentBody,
    ReportManualIncidentBody,
)


class SanitizeFrontendLogsTests(TestCase):

    def test_keeps_last_fifty(self):
        raw = [{'level': 'log', 'message': f'n{i}'} for i in range(80)]
        out = sanitize_frontend_logs(raw)
        self.assertEqual(len(out), FRONTEND_LOG_LIMIT)
        self.assertEqual(out[0]['message'], 'n30')
        self.assertEqual(out[-1]['message'], 'n79')

    def test_redacts_secret_pairs(self):
        out = sanitize_frontend_logs([
            {'level': 'error', 'message': 'login password=super-secret'},
        ])
        self.assertEqual(out[0]['message'], 'login password=***')

    def test_drops_empty_and_unknown_shapes(self):
        out = sanitize_frontend_logs([
            None,
            12,
            {'level': 'log', 'message': '   '},
            {'level': 'trace', 'message': 'ok', 'ts': '2026-01-01T00:00:00Z'},
        ])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['level'], 'log')
        self.assertEqual(out[0]['message'], 'ok')

    def test_accepts_plain_strings(self):
        out = sanitize_frontend_logs(['hello'])
        self.assertEqual(out, [{'ts': '', 'level': 'log', 'message': 'hello'}])

    def test_empty_input(self):
        self.assertEqual(sanitize_frontend_logs(None), [])
        self.assertEqual(sanitize_frontend_logs({}), [])

    def test_accepts_compact_header_shape(self):
        out = sanitize_frontend_logs([
            {'t': '2026-08-29T12:00:00Z', 'l': 'e', 'm': 'GET /x → 500'},
        ])
        self.assertEqual(out[0]['level'], 'error')
        self.assertEqual(out[0]['message'], 'GET /x → 500')
        self.assertEqual(out[0]['ts'], '2026-08-29T12:00:00Z')

    def test_decodes_base64_header(self):
        import base64
        import json
        from types import SimpleNamespace

        from platform.features.support.incidents.incident.application.frontend_logs import (
            frontend_logs_from_request,
        )

        payload = [{'t': '2026-08-29T12:00:00Z', 'l': 'w', 'm': 'slow'}]
        encoded = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('ascii')
        req = SimpleNamespace(META={'HTTP_X_WA_FRONTEND_LOGS': encoded})
        out = frontend_logs_from_request(req)
        self.assertEqual(out[0]['level'], 'warn')
        self.assertEqual(out[0]['message'], 'slow')


class ReportIncidentFrontendLogsBodyTests(TestCase):

    def test_draft_body_accepts_logs(self):
        body = ReportIncidentBody({
            'token': 'a' * 24,
            'comment': 'falló',
            'frontend_logs': [
                {'ts': '2026-08-29T12:00:00.000Z', 'level': 'error', 'message': 'boom'},
            ],
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['frontend_logs'][0]['level'], 'error')

    def test_manual_body_accepts_omitted_logs(self):
        body = ReportManualIncidentBody({
            'comment': 'algo anda mal',
            'conversation': {'messages': []},
            'source': 'toolbar',
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data.get('frontend_logs') or [], [])

    def test_rejects_too_many_logs(self):
        body = ReportIncidentBody({
            'token': 'a' * 24,
            'frontend_logs': [
                {'level': 'log', 'message': f'n{i}'} for i in range(51)
            ],
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(errors)
