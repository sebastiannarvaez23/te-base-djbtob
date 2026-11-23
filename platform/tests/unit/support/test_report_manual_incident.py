"""Unit tests de ReportManualIncidentUseCase (dobles en memoria, sin BD)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

from core.errors.exceptions import AppException
from platform.features.support.incidents.incident.application.report_manual_incident import (
    ASSISTANT_CHAT_FEATURE_KEY,
    ReportManualIncidentUseCase,
)
from platform.features.support.incidents.incident.domain.interfaces import (
    IFeatureRefResolver,
    IIncidentNotifier,
    IIncidentRepository,
    ISessionLogBuffer,
)
from platform.features.support.incidents.incident.domain.schemas import (
    IncidentView,
)


def _view(token, code='INC-2026-0100'):
    return IncidentView(id='id-' + token[:6], code=code, status='open', severity='medium')


class _FakeRepo(IIncidentRepository):
    def __init__(self):
        self.created = []
        self.by_token = {}

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


class _FakeBuffer(ISessionLogBuffer):
    def __init__(self, entries=None):
        self.entries = list(entries or [])

    def append_transaction(self, session_id, entry):  # pragma: no cover
        self.entries.append(entry)

    def snapshot(self, session_id):
        if not session_id:
            return []
        return list(self.entries)


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


class ReportManualIncidentUseCaseTests(TestCase):

    def test_assistant_report_uses_assistant_chat_refs(self):
        repo, buffer, notifier = _FakeRepo(), _FakeBuffer([
            {'request_id': 'r1', 'path': '/api/v1/orders/', 'logs': ['ok']},
            {'request_id': 'r2', 'path': '/api/v1/assistant/chat/', 'logs': ['chat']},
        ]), _FakeNotifier()
        resolver = _FakeFeatureResolver({
            ASSISTANT_CHAT_FEATURE_KEY: ('mod-assistant', 'fn-assistant'),
        })

        uc = ReportManualIncidentUseCase(
            repo, buffer, notifier,
            feature_resolver=resolver,
        )
        conversation = {
            'exported_at': '2026-08-25T12:00:00Z',
            'conversation_id': 'c1',
            'ui_context': {
                'route': '/warehouse/inventories',
                'module_name': 'Inventarios',
                'page_section': 'references',
            },
            'messages': [
                {'id': 'm1', 'role': 'user', 'text': 'hola'},
                {'id': 'm2', 'role': 'assistant', 'text': 'hola'},
            ],
        }
        incident = uc.execute(
            session_id='sid-1',
            comment='El asistente respondió mal',
            conversation=conversation,
            ui_context={
                'route': '/warehouse/inventories',
                'module_name': 'Inventarios',
                'page_section': 'references',
            },
            reporter={'username': 'ana', 'user_id': 'u1', 'schema_name': 'arisoft'},
            source='assistant',
        )

        self.assertEqual(len(repo.created), 1)
        data = repo.created[0]
        self.assertEqual(data.user_comment, 'El asistente respondió mal')
        self.assertEqual(data.severity, 'medium')
        self.assertEqual(data.module_id, 'mod-assistant')
        self.assertEqual(data.functionality_id, 'fn-assistant')
        self.assertEqual(data.page_section, 'references')
        self.assertEqual(data.snapshot['source'], 'assistant')
        self.assertEqual(
            data.snapshot['failed_request']['feature_key'],
            ASSISTANT_CHAT_FEATURE_KEY,
        )
        self.assertEqual(data.snapshot['conversation'], conversation)
        self.assertEqual(len(data.snapshot['last_transactions']), 2)
        self.assertEqual(data.error['code'], 'ASSISTANT_REPORT')
        self.assertEqual(data.error['feature_key'], ASSISTANT_CHAT_FEATURE_KEY)
        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(incident.code, 'INC-2026-0100')
        self.assertEqual(resolver.calls, [ASSISTANT_CHAT_FEATURE_KEY])

    def test_toolbar_report_keeps_page_context(self):
        repo, buffer, notifier = _FakeRepo(), _FakeBuffer(), _FakeNotifier()
        resolver = _FakeFeatureResolver({
            'orders.view': ('mod-page', 'fn-page'),
        })

        uc = ReportManualIncidentUseCase(
            repo, buffer, notifier, feature_resolver=resolver,
        )
        uc.execute(
            session_id='sid-1',
            comment='Falla al guardar pedido',
            conversation={'messages': []},
            ui_context={
                'route': '/warehouse/orders',
                'module_id': 'mod-page',
                'feature_key': 'orders.view',
                'page_section': 'orders',
            },
            source='toolbar',
        )
        data = repo.created[0]
        self.assertEqual(data.module_id, 'mod-page')
        self.assertEqual(data.functionality_id, 'fn-page')
        self.assertEqual(data.page_section, 'orders')
        self.assertEqual(data.snapshot['source'], 'toolbar')
        self.assertEqual(data.error['code'], 'TOOLBAR_REPORT')
        self.assertEqual(resolver.calls, ['orders.view'])

    def test_toolbar_suggestion_is_persisted_with_low_severity(self):
        repo, buffer, notifier = _FakeRepo(), _FakeBuffer(), _FakeNotifier()
        uc = ReportManualIncidentUseCase(repo, buffer, notifier)
        uc.execute(
            session_id='sid-1',
            comment='Agregar filtro por cliente\n\nSería útil en pedidos',
            conversation={'messages': []},
            ui_context={'route': '/warehouse/orders'},
            source='toolbar',
            kind='suggestion',
        )
        data = repo.created[0]
        self.assertEqual(data.kind, 'suggestion')
        self.assertEqual(data.severity, 'low')
        self.assertEqual(data.error['code'], 'TOOLBAR_SUGGESTION')
        self.assertEqual(data.snapshot['kind'], 'suggestion')
        self.assertEqual(len(notifier.calls), 1)

    def test_toolbar_report_defaults_to_incident_kind(self):
        repo = _FakeRepo()
        uc = ReportManualIncidentUseCase(repo, _FakeBuffer(), _FakeNotifier())
        uc.execute(session_id='', comment='Falla', conversation={'messages': []}, source='toolbar')
        self.assertEqual(repo.created[0].kind, 'incident')
        self.assertEqual(repo.created[0].severity, 'medium')

    def test_rejects_suggestion_outside_toolbar(self):
        repo = _FakeRepo()
        uc = ReportManualIncidentUseCase(repo, _FakeBuffer(), _FakeNotifier())
        with self.assertRaises(AppException):
            uc.execute(
                session_id='', comment='Idea', conversation={'messages': []},
                source='assistant', kind='suggestion',
            )
        self.assertEqual(repo.created, [])

    def test_rejects_unknown_kind(self):
        uc = ReportManualIncidentUseCase(_FakeRepo(), _FakeBuffer(), _FakeNotifier())
        with self.assertRaises(AppException):
            uc.execute(
                session_id='', comment='x', conversation={'messages': []},
                source='toolbar', kind='praise',
            )

    def test_rejects_empty_comment(self):
        uc = ReportManualIncidentUseCase(_FakeRepo(), _FakeBuffer(), _FakeNotifier())
        with self.assertRaises(AppException):
            uc.execute(
                session_id='sid',
                comment='   ',
                conversation={'messages': []},
            )

    def test_rejects_oversized_conversation(self):
        huge = {'messages': [{'id': '1', 'role': 'user', 'text': 'x' * 210_000}]}
        uc = ReportManualIncidentUseCase(_FakeRepo(), _FakeBuffer(), _FakeNotifier())
        with self.assertRaises(AppException):
            uc.execute(session_id='sid', comment='ok', conversation=huge)

    def test_works_without_session_logs(self):
        repo, buffer, notifier = _FakeRepo(), _FakeBuffer(), _FakeNotifier()
        resolver = _FakeFeatureResolver({
            ASSISTANT_CHAT_FEATURE_KEY: ('', ''),
        })
        uc = ReportManualIncidentUseCase(
            repo, buffer, notifier, feature_resolver=resolver,
        )
        uc.execute(
            session_id='',
            comment='Sin sesión',
            conversation={'messages': []},
            reporter={'username': 'ana'},
            source='assistant',
        )
        self.assertEqual(repo.created[0].snapshot['last_transactions'], [])

    def test_attaches_browser_console(self):
        repo, buffer, notifier = _FakeRepo(), _FakeBuffer(), _FakeNotifier()
        uc = ReportManualIncidentUseCase(repo, buffer, notifier)
        uc.execute(
            session_id='sid',
            comment='Sin sesión',
            conversation={'messages': []},
            source='toolbar',
            frontend_logs=[
                {'ts': '2026-08-29T12:00:00.000Z', 'level': 'warn', 'message': 'slow paint'},
            ],
        )
        stored = repo.created[0].snapshot['frontend_context']['browser_console']
        self.assertEqual(stored[0]['level'], 'warn')
        self.assertEqual(stored[0]['message'], 'slow paint')
