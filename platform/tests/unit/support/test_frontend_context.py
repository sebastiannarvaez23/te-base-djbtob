"""Unit tests for frontend context sanitization."""
import json

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import patch

from platform.features.support.incidents.incident.application.frontend_context import (
    FRONTEND_CONTEXT_MAX_BYTES,
    build_frontend_context_snapshot,
    sanitize_frontend_context,
)
from platform.features.support.incidents.incident.application.frontend_logs import BROWSER_CONSOLE_LIMIT
from platform.features.support.incidents.incident.presentation.bodies import (
    ReportIncidentBody,
    ReportManualIncidentBody,
)
from platform.features.support.incidents.incident.presentation.frontend_context_bodies import (
    FRONTEND_CONTEXT_REQUEST_MAX_BYTES,
)


class FrontendContextSanitizerTests(TestCase):

    def test_empty_input_returns_empty_dict(self):
        self.assertEqual(sanitize_frontend_context(None), {})
        self.assertEqual(sanitize_frontend_context('bad'), {})

    def test_redacts_sensitive_keys(self):
        raw = {
            'session': {'access_token': 'abc123', 'user_id': '42'},
            'recent_events': [
                {'ts': 't', 'type': 'API_ERROR', 'summary': 'password=secret'},
            ],
        }
        cleaned = sanitize_frontend_context(raw)
        self.assertEqual(cleaned['session']['access_token'], '***')
        self.assertEqual(cleaned['session']['user_id'], '42')
        self.assertIn('***', cleaned['recent_events'][0]['summary'])

    def test_clamps_list_sizes(self):
        events = [
            {'ts': f't{i}', 'type': 'NAVIGATION', 'summary': f'route-{i}'}
            for i in range(60)
        ]
        cleaned = sanitize_frontend_context({'recent_events': events})
        self.assertEqual(len(cleaned['recent_events']), 50)

    def test_clamps_browser_console(self):
        console = [
            {'ts': '', 'level': 'log', 'message': f'line-{i}'}
            for i in range(BROWSER_CONSOLE_LIMIT + 10)
        ]
        cleaned = sanitize_frontend_context({'browser_console': console})
        self.assertEqual(len(cleaned['browser_console']), BROWSER_CONSOLE_LIMIT)

    def test_clamps_navigation_routes(self):
        routes = [{'ts': f't{i}', 'route': f'/r{i}'} for i in range(15)]
        cleaned = sanitize_frontend_context({'navigation': {'recent_routes': routes}})
        self.assertEqual(len(cleaned['navigation']['recent_routes']), 10)

    def test_clamps_runtime_errors(self):
        errors = [{'ts': f't{i}', 'message': f'err-{i}'} for i in range(15)]
        cleaned = sanitize_frontend_context({'runtime': {'recent_errors': errors}})
        self.assertEqual(len(cleaned['runtime']['recent_errors']), 10)

    def test_does_not_mutate_input_lists(self):
        events = [
            {'ts': f't{i}', 'type': 'NAVIGATION', 'summary': f'route-{i}'}
            for i in range(60)
        ]
        raw = {'recent_events': events}
        sanitize_frontend_context(raw)
        self.assertEqual(len(raw['recent_events']), 60)

    def test_marks_truncated_when_payload_still_too_large(self):
        huge = 'x' * 400
        raw = {
            'recent_events': [
                {'ts': 't', 'type': 'API_ERROR', 'summary': huge}
                for _ in range(50)
            ],
        }
        with patch(
            'platform.features.support.incidents.incident.application.frontend_context.FRONTEND_CONTEXT_MAX_BYTES',
            1000,
        ):
            cleaned = sanitize_frontend_context(raw)
        self.assertTrue(cleaned.get('truncated'))

    def test_preserves_correlation_fields(self):
        raw = {
            'correlation_id': 'req-abc',
            'trace_id': 'req-abc',
            'application': {'name': 'base Client Web', 'environment': 'dev'},
        }
        cleaned = sanitize_frontend_context(raw)
        self.assertEqual(cleaned['correlation_id'], 'req-abc')
        self.assertEqual(cleaned['application']['name'], 'base Client Web')


class BuildFrontendContextSnapshotTests(TestCase):

    def test_returns_empty_when_no_input(self):
        self.assertEqual(build_frontend_context_snapshot(), {})

    def test_merges_browser_console_sources(self):
        ctx = {
            'correlation_id': 'abc',
            'browser_console': [{'level': 'info', 'message': 'from ctx', 'ts': ''}],
        }
        result = build_frontend_context_snapshot(
            ctx,
            legacy_frontend_logs=[{'level': 'warn', 'message': 'legacy', 'ts': ''}],
            draft_frontend_logs=[{'level': 'error', 'message': 'draft', 'ts': ''}],
        )
        self.assertEqual(result['correlation_id'], 'abc')
        self.assertEqual(len(result['browser_console']), 3)
        self.assertEqual(result['browser_console'][-1]['message'], 'legacy')

    def test_omits_browser_console_when_empty(self):
        result = build_frontend_context_snapshot({'trace_id': 't1'})
        self.assertNotIn('browser_console', result)

    def test_redacts_legacy_logs_during_merge(self):
        result = build_frontend_context_snapshot(
            None,
            legacy_frontend_logs=[
                {'level': 'error', 'message': 'token=abc123 failed', 'ts': ''},
            ],
        )
        self.assertIn('token=***', result['browser_console'][0]['message'])


class FrontendContextBodyTests(TestCase):

    def test_report_body_accepts_valid_frontend_context(self):
        body = ReportIncidentBody({
            'token': 'a' * 24,
            'frontend_context': {
                'trace_id': 'trace-1',
                'recent_events': [
                    {'type': 'NAVIGATION', 'summary': '/orders'},
                ],
            },
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)
        self.assertEqual(body.validated_data['frontend_context']['trace_id'], 'trace-1')

    def test_report_body_rejects_invalid_event_shape(self):
        body = ReportIncidentBody({
            'token': 'a' * 24,
            'frontend_context': {
                'recent_events': [{'type': 'NAVIGATION'}],
            },
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_frontend_context_size_errors_detects_oversized_payload(self):
        from platform.features.support.incidents.incident.presentation.frontend_context_bodies import (
            frontend_context_size_errors,
        )

        errors = frontend_context_size_errors(
            'frontend_context',
            {'blob': 'x' * (FRONTEND_CONTEXT_REQUEST_MAX_BYTES + 1)},
        )
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, 'frontend_context')

    def test_report_body_rejects_oversized_frontend_context(self):
        body = ReportIncidentBody({
            'token': 'a' * 24,
            'frontend_context': {
                'recent_events': [
                    {'type': 'API_ERROR', 'summary': 'x' * 400}
                    for _ in range(10)
                ],
            },
        })
        with patch(
            'platform.features.support.incidents.incident.presentation.frontend_context_bodies.FRONTEND_CONTEXT_REQUEST_MAX_BYTES',
            1000,
        ):
            ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(any(err.field == 'frontend_context' for err in errors))

    def test_manual_body_rejects_invalid_frontend_log_entry(self):
        body = ReportManualIncidentBody({
            'comment': 'falló',
            'conversation': {'messages': []},
            'frontend_logs': [{'level': 'error'}],
        })
        ok, errors = body.validate()
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_manual_body_accepts_structured_frontend_context(self):
        body = ReportManualIncidentBody({
            'comment': 'falló',
            'conversation': {'messages': []},
            'frontend_context': {
                'browser_console': [
                    {'level': 'warn', 'message': 'slow paint'},
                ],
            },
        })
        ok, errors = body.validate()
        self.assertTrue(ok, errors)

    def test_serialized_context_within_storage_budget_after_sanitize(self):
        payload = {
            'recent_events': [
                {'ts': 't', 'type': 'API_ERROR', 'summary': 'x' * 400}
                for _ in range(50)
            ],
        }
        cleaned = sanitize_frontend_context(payload)
        size = len(json.dumps(cleaned, ensure_ascii=False).encode('utf-8'))
        self.assertLessEqual(size, FRONTEND_CONTEXT_MAX_BYTES + 500)
