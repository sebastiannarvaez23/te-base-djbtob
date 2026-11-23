"""Unit tests de CreateIncidentDraftUseCase (con buffer y draft store falsos)."""
from unittest import TestCase

from platform.features.support.incidents.incident.application.create_draft import (
    CreateIncidentDraftUseCase,
)
from platform.features.support.incidents.incident.domain.interfaces import (
    IIncidentDraftStore,
    ISessionLogBuffer,
)


class _FakeBuffer(ISessionLogBuffer):
    def __init__(self, snap):
        self._snap = snap

    def append_transaction(self, session_id, entry):  # pragma: no cover
        pass

    def snapshot(self, session_id):
        return self._snap


class _FakeDraftStore(IIncidentDraftStore):
    def __init__(self):
        self.saved = None

    def save(self, token, draft):
        self.saved = (token, draft)

    def pop(self, token):  # pragma: no cover
        return None


class CreateIncidentDraftUseCaseTests(TestCase):

    def setUp(self):
        self.snapshot = [{'request_id': f'r{i}'} for i in range(10)]
        self.buffer = _FakeBuffer(self.snapshot)
        self.store = _FakeDraftStore()
        self.uc = CreateIncidentDraftUseCase(self.buffer, self.store)
        self.failed = {'request_id': 'r-fail', 'path': '/x/', 'logs': ['boom']}
        self.error = {'code': 'SRV_001', 'exception_type': 'ValueError'}

    def test_builds_draft_with_last_transactions_failed_and_error(self):
        failed = {
            **self.failed,
            'module_id': 'mod-1',
            'functionality_id': 'fn-1',
            'page_section': 'company',
        }
        token = self.uc.execute('sid', failed_request=failed, error=self.error)
        self.assertTrue(token)
        saved_token, draft = self.store.saved
        self.assertEqual(saved_token, token)
        self.assertEqual(draft['session_id'], 'sid')
        self.assertEqual(draft['last_transactions'], self.snapshot)   # las 10
        self.assertEqual(draft['failed_request'], failed)
        self.assertEqual(draft['failed_request']['page_section'], 'company')
        self.assertEqual(draft['error'], self.error)
        self.assertEqual(draft['frontend_logs'], [])
        self.assertIn('created_at', draft)

    def test_token_is_opaque_and_unique(self):
        t1 = self.uc.execute('sid', failed_request=self.failed, error=self.error)
        t2 = self.uc.execute('sid', failed_request=self.failed, error=self.error)
        self.assertNotEqual(t1, t2)
        self.assertGreater(len(t1), 20)

    def test_noop_without_session(self):
        token = self.uc.execute('', failed_request=self.failed, error=self.error)
        self.assertEqual(token, '')
        self.assertIsNone(self.store.saved)

    def test_persists_frontend_logs(self):
        token = self.uc.execute(
            'sid',
            failed_request=self.failed,
            error=self.error,
            frontend_logs=[{'level': 'error', 'message': 'GET /x → 500'}],
        )
        self.assertTrue(token)
        self.assertEqual(
            self.store.saved[1]['frontend_logs'][0]['message'],
            'GET /x → 500',
        )
