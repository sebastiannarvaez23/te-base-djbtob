"""Unit tests de CaptureTransactionUseCase (con un buffer en memoria)."""
from unittest import TestCase

from platform.features.support.incidents.incident.application.capture_transaction import (
    CaptureTransactionUseCase,
)
from platform.features.support.incidents.incident.domain.interfaces import ISessionLogBuffer


class _FakeBuffer(ISessionLogBuffer):
    def __init__(self):
        self.appended = []

    def append_transaction(self, session_id, entry):
        self.appended.append((session_id, entry))

    def snapshot(self, session_id):
        return [e.model_dump() for sid, e in self.appended if sid == session_id]


class CaptureTransactionUseCaseTests(TestCase):

    def setUp(self):
        self.buffer = _FakeBuffer()
        self.uc = CaptureTransactionUseCase(self.buffer)

    def test_builds_entry_with_all_fields(self):
        self.uc.execute(
            'sid-1',
            request_id='req-1', ts='2026-07-01T10:00:00+00:00', origin='app',
            method='POST', path='/api/v1/x/', query='a=1',
            request_body='{"a":1}', status=200, response_body='{"ok":true}',
            duration_ms=42.1, logs=['>> REQ', '<< RES'],
            module_id='mod-1', module_code='ORDERS', functionality_id='fn-1',
            page_section='profile', feature_key='settings.profile.edit',
        )
        self.assertEqual(len(self.buffer.appended), 1)
        sid, entry = self.buffer.appended[0]
        self.assertEqual(sid, 'sid-1')
        self.assertEqual(entry.request_id, 'req-1')
        self.assertEqual(entry.method, 'POST')
        self.assertEqual(entry.status, 200)
        self.assertEqual(entry.logs, ['>> REQ', '<< RES'])
        self.assertEqual(entry.module_id, 'mod-1')
        self.assertEqual(entry.module_code, 'ORDERS')
        self.assertEqual(entry.functionality_id, 'fn-1')
        self.assertEqual(entry.page_section, 'profile')
        self.assertEqual(entry.feature_key, 'settings.profile.edit')

    def test_noop_without_session_id(self):
        self.uc.execute('', request_id='r', ts='t')
        self.assertEqual(self.buffer.appended, [])

    def test_logs_default_to_empty_list(self):
        self.uc.execute('sid', request_id='r', ts='t')
        _, entry = self.buffer.appended[0]
        self.assertEqual(entry.logs, [])
