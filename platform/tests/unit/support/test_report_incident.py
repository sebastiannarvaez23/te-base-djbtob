"""Unit tests de ReportIncidentUseCase (dobles en memoria, sin BD)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

from core.errors.codes import AppErrorCode
from core.errors.exceptions import AppException
from platform.features.support.incidents.incident.application.report_incident import (
    ReportIncidentUseCase,
)
from platform.features.support.incidents.incident.domain.interfaces import (
    IFeatureRefResolver,
    IIncidentDraftStore,
    IIncidentNotifier,
    IIncidentRepository,
)
from platform.features.support.incidents.incident.domain.schemas import IncidentView


def _view(token, code='INC-2026-0001'):
    return IncidentView(id='id-' + token[:6], code=code, status='open', severity='high')


class _FakeRepo(IIncidentRepository):
    def __init__(self, existing=None):
        self.by_token = dict(existing or {})
        self.created = []

    def create(self, data):
        self.created.append(data)
        v = _view(data.token)
        self.by_token[data.token] = v
        return v

    def get_by_token(self, token):
        return self.by_token.get(token)

    def get(self, incident_id):  # pragma: no cover
        return None

    def list(self, filters, limit=50, offset=0):  # pragma: no cover
        return []

    def update_status(self, incident_id, **kw):  # pragma: no cover
        return None

    def count(self, filters):  # pragma: no cover
        return len(self.by_token)

    def purge(self, before, statuses):  # pragma: no cover
        return 0


class _FakeDraftStore(IIncidentDraftStore):
    def __init__(self, drafts=None):
        self.drafts = dict(drafts or {})

    def save(self, token, draft):  # pragma: no cover
        self.drafts[token] = draft

    def pop(self, token):
        return self.drafts.pop(token, None)


class _FakeNotifier(IIncidentNotifier):
    def __init__(self):
        self.calls = []

    def notify_created(self, incident):
        self.calls.append(incident)


class _FakeFeatureResolver(IFeatureRefResolver):
    def __init__(self, mapping=None):
        self._mapping = mapping or {}
        self.calls = []

    def resolve(self, feature_key):
        self.calls.append(feature_key)
        return self._mapping.get(feature_key, ('', ''))


_DRAFT = {
    'session_id': 'sid-1',
    'error': {'code': 'SRV_001', 'exception_type': 'ValueError'},
    'failed_request': {
        'request_id': 'r-fail',
        'logs': ['boom'],
        'module_id': 'mod-uuid',
        'functionality_id': 'fn-uuid',
        'page_section': 'profile',
    },
    'last_transactions': [{'request_id': f'r{i}'} for i in range(10)],
}


class ReportIncidentUseCaseTests(TestCase):

    def _uc(self, repo, store, notifier):
        return ReportIncidentUseCase(repo, store, notifier)

    def test_builds_incident_with_snapshot_and_notifies_once(self):
        repo, store, notifier = _FakeRepo(), _FakeDraftStore({'tok': dict(_DRAFT)}), _FakeNotifier()
        incident = self._uc(repo, store, notifier).execute(
            'tok', comment='no cargó', reporter={'username': 'ana', 'schema_name': 'arisoft'})

        self.assertEqual(len(repo.created), 1)
        data = repo.created[0]
        self.assertEqual(data.snapshot['last_transactions'], _DRAFT['last_transactions'])  # 10
        self.assertEqual(data.snapshot['failed_request'], _DRAFT['failed_request'])          # + fallida
        self.assertEqual(data.snapshot.get('frontend_logs'), None)
        self.assertEqual(data.snapshot.get('frontend_context', {}).get('browser_console'), None)
        self.assertEqual(data.error, _DRAFT['error'])
        self.assertEqual(data.user_comment, 'no cargó')
        self.assertEqual(data.reporter_username, 'ana')
        self.assertEqual(data.module_id, 'mod-uuid')
        self.assertEqual(data.functionality_id, 'fn-uuid')
        self.assertEqual(data.page_section, 'profile')
        self.assertEqual(len(notifier.calls), 1)                # notifica exactamente una vez
        self.assertEqual(incident.code, 'INC-2026-0001')
        self.assertNotIn('tok', store.drafts)                   # draft consumido

    def test_idempotent_when_already_reported(self):
        existing = _view('tok', code='INC-2026-0009')
        repo = _FakeRepo(existing={'tok': existing})
        store, notifier = _FakeDraftStore({'tok': dict(_DRAFT)}), _FakeNotifier()

        result = self._uc(repo, store, notifier).execute('tok')

        self.assertEqual(result.code, 'INC-2026-0009')
        self.assertEqual(repo.created, [])          # no crea otra
        self.assertEqual(notifier.calls, [])        # no re-notifica
        self.assertIn('tok', store.drafts)          # no consume el draft

    def test_missing_draft_raises_410_not_500(self):
        repo, store, notifier = _FakeRepo(), _FakeDraftStore({}), _FakeNotifier()
        with self.assertRaises(AppException) as ctx:
            self._uc(repo, store, notifier).execute('tok')
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_DRAFT_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 410)

    def test_empty_token_raises(self):
        with self.assertRaises(AppException):
            self._uc(_FakeRepo(), _FakeDraftStore(), _FakeNotifier()).execute('')

    def test_race_create_conflict_returns_existing(self):
        # get_by_token: None en el paso 1, luego la existente tras el IntegrityError.
        class RacyRepo(_FakeRepo):
            def __init__(self):
                super().__init__()
                self._calls = 0

            def get_by_token(self, token):
                self._calls += 1
                return None if self._calls == 1 else _view(token, code='INC-2026-0002')

            def create(self, data):
                raise Exception('duplicate key value violates unique constraint token')

        repo = RacyRepo()
        store, notifier = _FakeDraftStore({'tok': dict(_DRAFT)}), _FakeNotifier()
        result = self._uc(repo, store, notifier).execute('tok')
        self.assertEqual(result.code, 'INC-2026-0002')
        self.assertEqual(notifier.calls, [])   # no notifica en la carrera perdida

    def test_notifier_failure_still_returns_incident(self):
        class FailingNotifier(_FakeNotifier):
            def notify_created(self, incident):
                raise RuntimeError('email down')

        repo, store = _FakeRepo(), _FakeDraftStore({'tok': dict(_DRAFT)})
        incident = self._uc(repo, store, FailingNotifier()).execute('tok')
        self.assertEqual(incident.code, 'INC-2026-0001')
        self.assertEqual(len(repo.created), 1)

    def test_resolves_feature_key_when_functionality_id_missing(self):
        draft = {
            'session_id': 'sid-1',
            'error': {'code': 'SRV_001', 'ui_context': {}},
            'failed_request': {
                'request_id': 'r-fail',
                'feature_key': 'orders.view',
                'page_section': 'list',
            },
            'last_transactions': [],
        }
        resolver = _FakeFeatureResolver({'orders.view': ('mod-r', 'fn-r')})
        repo = _FakeRepo()
        store = _FakeDraftStore({'tok': draft})
        incident = ReportIncidentUseCase(
            repo, store, _FakeNotifier(), feature_resolver=resolver,
        ).execute('tok')

        data = repo.created[0]
        self.assertEqual(data.module_id, 'mod-r')
        self.assertEqual(data.functionality_id, 'fn-r')
        self.assertEqual(data.page_section, 'list')
        self.assertEqual(resolver.calls, ['orders.view'])
        self.assertEqual(incident.code, 'INC-2026-0001')

    def test_skips_resolve_when_functionality_id_already_present(self):
        resolver = _FakeFeatureResolver({'orders.view': ('mod-r', 'fn-r')})
        repo = _FakeRepo()
        store = _FakeDraftStore({'tok': dict(_DRAFT)})
        ReportIncidentUseCase(
            repo, store, _FakeNotifier(), feature_resolver=resolver,
        ).execute('tok')
        self.assertEqual(resolver.calls, [])
        self.assertEqual(repo.created[0].functionality_id, 'fn-uuid')

    def test_attaches_sanitized_browser_console(self):
        repo, store, notifier = _FakeRepo(), _FakeDraftStore({'tok': dict(_DRAFT)}), _FakeNotifier()
        logs = [
            {'ts': '2026-08-29T12:00:00.000Z', 'level': 'info', 'message': 'boot'},
            {'ts': '2026-08-29T12:00:01.000Z', 'level': 'error', 'message': 'token=abc123 failed'},
        ]
        self._uc(repo, store, notifier).execute('tok', frontend_logs=logs)
        stored = repo.created[0].snapshot['frontend_context']['browser_console']
        self.assertEqual(len(stored), 2)
        self.assertEqual(stored[0]['message'], 'boot')
        self.assertEqual(stored[1]['message'], 'token=*** failed')
        self.assertEqual(stored[1]['level'], 'error')

    def test_uses_draft_browser_console_when_post_omits_them(self):
        draft = dict(_DRAFT)
        draft['frontend_logs'] = [
            {'ts': '2026-08-29T12:00:00.000Z', 'level': 'error', 'message': 'GET /x/ → 500 SRV_001'},
        ]
        repo, store, notifier = _FakeRepo(), _FakeDraftStore({'tok': draft}), _FakeNotifier()
        self._uc(repo, store, notifier).execute('tok')
        stored = repo.created[0].snapshot['frontend_context']['browser_console']
        self.assertEqual(len(stored), 1)
        self.assertIn('GET /x/', stored[0]['message'])
