"""Unit tests de UpdateIncidentStatusUseCase + OutboxIncidentReporterNotifier."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import MagicMock

from platform.features.communication.messaging.inbox.domain.enums import (
    AudienceScope,
    NotificationLevel,
)
from platform.features.support.incidents.incident.application.admin_use_cases import (
    UpdateIncidentStatusUseCase,
)
from platform.features.support.incidents.incident.domain.interfaces import (
    IIncidentReporterNotifier,
    IIncidentRepository,
)
from platform.features.support.incidents.incident.domain.schemas import IncidentView
from platform.features.support.incidents.incident.infrastructure.reporter_inbox_notifier import (
    OutboxIncidentReporterNotifier,
)


def _view(**overrides):
    base = dict(
        id='inc-1',
        code='INC-2026-0001',
        status='open',
        severity='medium',
        reporter_user_id='11111111-1111-1111-1111-111111111111',
        resolution_notes='',
    )
    base.update(overrides)
    return IncidentView(**base)


class _FakeRepo(IIncidentRepository):
    def __init__(self, current: IncidentView):
        self.current = current
        self.updated_with = None

    def create(self, data):  # pragma: no cover
        raise NotImplementedError

    def get_by_token(self, token):  # pragma: no cover
        return None

    def get(self, incident_id):
        return self.current if incident_id == self.current.id else None

    def list(self, filters, limit=50, offset=0):  # pragma: no cover
        return []

    def count(self, filters):  # pragma: no cover
        return 0

    def update_status(self, incident_id, *, status, assigned_admin_id=None,
                      resolution_notes=None):
        self.updated_with = {
            'status': status,
            'assigned_admin_id': assigned_admin_id,
            'resolution_notes': resolution_notes,
        }
        self.current = _view(
            id=self.current.id,
            code=self.current.code,
            status=status,
            reporter_user_id=self.current.reporter_user_id,
            resolution_notes=(
                resolution_notes
                if resolution_notes is not None
                else self.current.resolution_notes
            ),
            assigned_admin_id=assigned_admin_id or self.current.assigned_admin_id,
        )
        return self.current

    def purge(self, before, statuses):  # pragma: no cover
        return 0


class _FakeReporterNotifier(IIncidentReporterNotifier):
    def __init__(self):
        self.calls = []

    def notify_status_changed(self, incident, *, previous_status, admin_id, admin_label):
        self.calls.append({
            'incident': incident,
            'previous_status': previous_status,
            'admin_id': admin_id,
            'admin_label': admin_label,
        })


class UpdateIncidentStatusUseCaseTests(TestCase):

    def test_notifies_reporter_when_status_changes(self):
        repo = _FakeRepo(_view(status='open'))
        notifier = _FakeReporterNotifier()
        uc = UpdateIncidentStatusUseCase(repo, reporter_notifier=notifier)

        result = uc.execute(
            'inc-1',
            status='in_progress',
            assigned_admin_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            admin_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            admin_label='Ana Soporte',
        )

        self.assertEqual(result.status, 'in_progress')
        self.assertEqual(len(notifier.calls), 1)
        self.assertEqual(notifier.calls[0]['previous_status'], 'open')
        self.assertEqual(notifier.calls[0]['admin_label'], 'Ana Soporte')

    def test_skips_notify_when_status_unchanged(self):
        repo = _FakeRepo(_view(status='open'))
        notifier = _FakeReporterNotifier()
        uc = UpdateIncidentStatusUseCase(repo, reporter_notifier=notifier)

        uc.execute('inc-1', status='open', resolution_notes='solo nota')
        self.assertEqual(notifier.calls, [])


class OutboxIncidentReporterNotifierTests(TestCase):

    def test_queues_single_user_outbox(self):
        notify_uc = MagicMock()
        notifier = OutboxIncidentReporterNotifier(notify_uc)
        incident = _view(
            status='resolved',
            resolution_notes='Ya quedó corregido',
        )

        notifier.notify_status_changed(
            incident,
            previous_status='in_progress',
            admin_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            admin_label='Ana',
        )

        notify_uc.execute.assert_called_once()
        payload = notify_uc.execute.call_args.args[0]
        self.assertEqual(payload.audience.scope, AudienceScope.SINGLE_USER)
        self.assertEqual(
            str(payload.audience.target_user_id),
            '11111111-1111-1111-1111-111111111111',
        )
        self.assertEqual(payload.level, NotificationLevel.SUCCESS)
        self.assertIn('INC-2026-0001', payload.title)
        self.assertIn('Resuelta', payload.title)
        self.assertIn('Ya quedó corregido', payload.body)

    def test_skips_system_reporter(self):
        notify_uc = MagicMock()
        notifier = OutboxIncidentReporterNotifier(notify_uc)
        notifier.notify_status_changed(
            _view(status='closed', reporter_user_id='system'),
            previous_status='open',
            admin_id='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            admin_label='Ana',
        )
        notify_uc.execute.assert_not_called()
