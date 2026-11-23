"""Unit tests de los casos de uso admin (List / Get / UpdateStatus)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

from core.errors.codes import AppErrorCode
from core.errors.exceptions import AppException
from platform.features.support.incidents.incident.application.admin_use_cases import (
    GetIncidentUseCase,
    ListIncidentsUseCase,
    UpdateIncidentStatusUseCase,
)
from platform.features.support.incidents.incident.application.purge_incidents import (
    PurgeIncidentsUseCase,
)
from platform.features.support.incidents.incident.domain.interfaces import IIncidentRepository
from platform.features.support.incidents.incident.domain.schemas import IncidentView


def _view(code='INC-2026-0001', status='open', **extra):
    data = dict(id='i-1', code=code, status=status, severity='high')
    data.update(extra)
    return IncidentView(**data)


class _FakeRepo(IIncidentRepository):
    def __init__(self, get_result=None, update_result='__self__'):
        self._get = get_result
        self._update = update_result
        self.list_args = None
        self.update_args = None

    def create(self, data):  # pragma: no cover
        return _view()

    def get_by_token(self, token):  # pragma: no cover
        return None

    def get(self, incident_id):
        return self._get

    def list(self, filters, limit=50, offset=0):
        self.list_args = (filters, limit, offset)
        return [_view()]

    def count(self, filters):
        return 1

    def update_status(self, incident_id, *, status, assigned_admin_id=None, resolution_notes=None):
        self.update_args = dict(incident_id=incident_id, status=status,
                                assigned_admin_id=assigned_admin_id,
                                resolution_notes=resolution_notes)
        if self._update == '__self__':
            return _view(status=status)
        return self._update

    def purge(self, before, statuses):
        self.purge_args = (before, statuses)
        return 7


class ListIncidentsUseCaseTests(TestCase):
    def test_passes_filters_and_pagination(self):
        repo = _FakeRepo()
        result = ListIncidentsUseCase(repo).execute({'status': 'open'}, limit=10, offset=20)
        self.assertEqual(repo.list_args, ({'status': 'open'}, 10, 20))
        self.assertEqual(len(result), 1)


class GetIncidentUseCaseTests(TestCase):
    def test_returns_incident(self):
        inc = GetIncidentUseCase(_FakeRepo(get_result=_view())).execute('i-1')
        self.assertEqual(inc.code, 'INC-2026-0001')

    def test_raises_404_when_missing(self):
        with self.assertRaises(AppException) as ctx:
            GetIncidentUseCase(_FakeRepo(get_result=None)).execute('nope')
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_NOT_FOUND)
        self.assertEqual(ctx.exception.http_status, 404)


class UpdateIncidentStatusUseCaseTests(TestCase):
    def test_valid_status_updates(self):
        repo = _FakeRepo(get_result=_view(status='in_progress', assigned_admin_id='admin-1'))
        inc = UpdateIncidentStatusUseCase(repo).execute(
            'i-1', status='resolved', resolution_notes='fixed')
        self.assertEqual(inc.status, 'resolved')
        self.assertEqual(repo.update_args['status'], 'resolved')
        self.assertEqual(repo.update_args['resolution_notes'], 'fixed')

    def test_invalid_status_rejected(self):
        with self.assertRaises(AppException) as ctx:
            UpdateIncidentStatusUseCase(
                _FakeRepo(get_result=_view()),
            ).execute('i-1', status='bogus')
        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)

    def test_not_found_raises_404(self):
        repo = _FakeRepo(get_result=None, update_result=None)
        with self.assertRaises(AppException) as ctx:
            UpdateIncidentStatusUseCase(repo).execute('nope', status='closed')
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_NOT_FOUND)

    def test_not_found_on_update_raises_404(self):
        repo = _FakeRepo(
            get_result=_view(status='in_progress', assigned_admin_id='admin-1'),
            update_result=None,
        )
        with self.assertRaises(AppException) as ctx:
            UpdateIncidentStatusUseCase(repo).execute(
                'nope', status='closed', resolution_notes='done')
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_NOT_FOUND)

    def test_resolve_without_assignee_rejected(self):
        repo = _FakeRepo(get_result=_view(status='open'))
        with self.assertRaises(AppException) as ctx:
            UpdateIncidentStatusUseCase(repo).execute(
                'i-1', status='resolved', resolution_notes='fixed')
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_ASSIGNEE_REQUIRED)

    def test_close_without_notes_rejected(self):
        repo = _FakeRepo(get_result=_view(status='in_progress', assigned_admin_id='admin-1'))
        with self.assertRaises(AppException) as ctx:
            UpdateIncidentStatusUseCase(repo).execute('i-1', status='closed')
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_NOTES_REQUIRED)

    def test_in_progress_requires_assignee(self):
        repo = _FakeRepo(get_result=_view(status='open'))
        with self.assertRaises(AppException) as ctx:
            UpdateIncidentStatusUseCase(repo).execute('i-1', status='in_progress')
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_ASSIGNEE_REQUIRED)

    def test_assign_sets_in_progress(self):
        repo = _FakeRepo(get_result=_view(status='open'))
        inc = UpdateIncidentStatusUseCase(repo).execute(
            'i-1', status='in_progress', assigned_admin_id='admin-1')
        self.assertEqual(inc.status, 'in_progress')
        self.assertEqual(repo.update_args['assigned_admin_id'], 'admin-1')


class PurgeIncidentsUseCaseTests(TestCase):
    def test_purges_terminal_statuses_before_cutoff(self):
        repo = _FakeRepo()
        deleted = PurgeIncidentsUseCase(repo).execute(days=90)
        self.assertEqual(deleted, 7)
        before, statuses = repo.purge_args
        self.assertEqual(set(statuses), {'resolved', 'closed', 'discarded'})
        # cutoff ~ now - 90d (aprox: en el pasado)
        from django.utils import timezone
        self.assertLess(before, timezone.now())

    def test_custom_retention_days(self):
        repo = _FakeRepo()
        PurgeIncidentsUseCase(repo).execute(days=30)
        before, _ = repo.purge_args
        from django.utils import timezone
        from datetime import timedelta
        expected = timezone.now() - timedelta(days=30)
        self.assertAlmostEqual(before.timestamp(), expected.timestamp(), delta=5)

    def test_custom_statuses(self):
        repo = _FakeRepo()
        PurgeIncidentsUseCase(repo).execute(days=7, statuses={'closed'})
        _, statuses = repo.purge_args
        self.assertEqual(statuses, {'closed'})

