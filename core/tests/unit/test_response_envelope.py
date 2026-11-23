"""Contract tests for the API response envelope.

Every JSON response the backend emits — success, validation error,
business error — carries a ``type`` field. The frontend switches on
this without parsing status codes:

  * ``success`` — happy path (HTTP 2xx with ``data``).
  * ``warning`` — operation accepted with a caveat the UI should
    surface (e.g. registration accepted but welcome-email send failed).
  * ``error`` — produced by the validators or the global exception
    handler.

These tests pin the ``type`` field on every builder. Renaming or
dropping the field is a breaking change for the frontend integration.
"""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

from core.decorators.response import wrap_response, RESPONSE_TYPES
from core.errors.codes import AppErrorCode
from core.errors.exceptions import AppException
from core.errors.handler import app_exception_handler


class TestWrapResponse(TestCase):

    def test_default_type_is_success(self):
        """Most callers won't pass ``type`` explicitly — the default
        must be ``success`` so the happy path stays one-liner."""
        response = wrap_response({'id': 1})

        self.assertEqual(response.data['type'], 'success')

    def test_warning_type_is_accepted(self):
        """Use cases that succeed-with-caveat (best-effort step
        failed, deprecated endpoint, etc.) opt into ``warning``."""
        response = wrap_response({'id': 1}, type='warning')

        self.assertEqual(response.data['type'], 'warning')

    def test_unknown_type_is_rejected(self):
        """A typo at a call site shouldn't silently ship — the
        contract is closed to the documented values."""
        with self.assertRaises(ValueError):
            wrap_response({'id': 1}, type='succss')

    def test_envelope_carries_all_documented_fields(self):
        """The envelope contract: type, status_code, message,
        resolved_at, data. Frontend reads every one of these."""
        response = wrap_response({'id': 1}, status_code=201, message='Created')

        for key in ('type', 'status_code', 'message', 'resolved_at', 'data'):
            self.assertIn(key, response.data, msg=f'missing key: {key}')
        self.assertEqual(response.data['status_code'], 201)
        self.assertEqual(response.data['message'], 'Created')

    def test_datetime_payload_is_serialized_with_z(self):
        from datetime import datetime, timezone
        response = wrap_response({
            'at': datetime(2026, 1, 15, 19, 0, tzinfo=timezone.utc),
            'iso': '2026-01-15T19:00:00+00:00',
        })
        self.assertEqual(response.data['data']['at'], '2026-01-15T19:00:00Z')
        self.assertEqual(response.data['data']['iso'], '2026-01-15T19:00:00Z')

    def test_response_types_constant_lists_canonical_values(self):
        """The exported tuple is the source of truth for tests / docs.
        Adding a new type must come with a deliberate update here."""
        self.assertEqual(RESPONSE_TYPES, ('success', 'warning', 'error'))


class TestExceptionHandlerEnvelope(TestCase):

    def test_app_exception_returns_type_error(self):
        """Every error path through the global handler must include
        ``type='error'`` so the frontend's switch lands on the right
        branch without inspecting status codes."""
        exc = AppException(AppErrorCode.AUTH_INVALID_CREDENTIALS)

        response = app_exception_handler(exc, context={'request': None, 'view': None})

        self.assertEqual(response.data['type'], 'error')

    def test_unhandled_exception_returns_type_error(self):
        """Even the catch-all 500 path includes the type marker so a
        broken backend doesn't hand the frontend an envelope shape it
        can't handle."""
        response = app_exception_handler(
            RuntimeError('boom'), context={'request': None, 'view': None},
        )

        self.assertEqual(response.data['type'], 'error')
        self.assertEqual(response.data['status_code'], 500)
