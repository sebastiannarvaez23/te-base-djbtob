"""Unit tests de ReportTaskFailureUseCase (dobles en memoria)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase

import pytest

from platform.features.support.incidents.incident.application.report_task_failure import (
    ReportTaskFailureUseCase,
)
from platform.features.support.incidents.incident.domain.interfaces import (
    IIncidentNotifier,
    IIncidentRepository,
)
from platform.features.support.incidents.incident.domain.schemas import IncidentView

pytestmark = pytest.mark.unit


def _view(token, code='INC-2026-0099'):
    return IncidentView(id='id-' + token[:8], code=code, status='open', severity='high')


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


class _FakeNotifier(IIncidentNotifier):
    def __init__(self):
        self.calls = []

    def notify_created(self, incident):
        self.calls.append(incident)


class ReportTaskFailureTests(TestCase):

    def setUp(self):
        self.repo = _FakeRepo()
        self.notifier = _FakeNotifier()
        self.uc = ReportTaskFailureUseCase(self.repo, self.notifier)

    def test_creates_incident_with_only_task_logs(self):
        logs = ['task_failed task=demo.boom', 'renewal charge errored']
        incident = self.uc.execute(
            task_id='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
            task_name='subscription.renew_due_subscriptions',
            exc=RuntimeError('boom'),
            traceback_text='Traceback...',
            task_logs=logs,
            schema_name='acme',
        )

        self.assertEqual(incident.code, 'INC-2026-0099')
        self.assertEqual(len(self.repo.created), 1)
        data = self.repo.created[0]
        self.assertEqual(data.token, 'task-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        self.assertEqual(data.schema_name, 'acme')
        self.assertEqual(data.reporter_username, 'celery')
        self.assertEqual(data.snapshot['source'], 'automated_task')
        self.assertEqual(data.snapshot['last_transactions'], [])
        self.assertEqual(data.snapshot['failed_request']['logs'], logs)
        self.assertEqual(data.snapshot['failed_request']['method'], 'TASK')
        self.assertEqual(data.error['code'], 'TASK_FAIL')
        self.assertEqual(data.error['task_name'], 'subscription.renew_due_subscriptions')
        self.assertEqual(len(self.notifier.calls), 1)

    def test_idempotent_by_task_id_token(self):
        kwargs = dict(
            task_id='tid-1',
            task_name='demo.task',
            exc=ValueError('x'),
            task_logs=['a'],
        )
        first = self.uc.execute(**kwargs)
        second = self.uc.execute(**kwargs)
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.repo.created), 1)

    def test_excludes_notify_created_task(self):
        result = self.uc.execute(
            task_id='tid-2',
            task_name='incident.notify_created',
            exc=RuntimeError('x'),
            task_logs=['should-not-persist'],
        )
        self.assertIsNone(result)
        self.assertEqual(self.repo.created, [])
        self.assertEqual(self.notifier.calls, [])
