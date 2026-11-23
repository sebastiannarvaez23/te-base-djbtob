"""Unit tests for task-monitor admin API views (use cases patched)."""

from __future__ import annotations

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from platform.features.support.ops.task_monitor.domain.schemas import (
    TaskCardView,
    TaskRunLogsView,
    TaskRunSummaryView,
    TaskRunView,
    TaskStepDefView,
)
from platform.features.support.ops.task_monitor.presentation.admin_api import (
    MonitoredTaskListView,
    TaskRunDetailView,
    TaskRunListView,
    TaskRunLogsView as TaskRunLogsAPIView,
)

pytestmark = pytest.mark.unit

_MOD = 'platform.features.support.ops.task_monitor.presentation.admin_api'


def _card():
    return TaskCardView(
        key='onboarding.purge_expired',
        title='Purge expired onboardings',
        description='…',
        icon='bx-user-x',
        schedule_label='Daily 03:00 UTC',
        group='onboarding',
        steps=[TaskStepDefView(key='acquire_lock', label='Acquire lock', icon='bx-lock', order=1)],
        last_run=None,
        recent_success_count=0,
        recent_failed_count=0,
        is_running=False,
    )


def _summary(run_id=None):
    return TaskRunSummaryView(
        id=run_id or uuid4(),
        task_key='onboarding.purge_expired',
        status='success',
        is_retry=False,
        retry_count=0,
        trigger='beat',
    )


def _run(run_id=None):
    rid = run_id or uuid4()
    return TaskRunView(
        id=rid,
        task_key='onboarding.purge_expired',
        status='failed',
        error_summary='boom | rolled back',
        steps=[],
    )


def _logs(run_id=None):
    rid = run_id or uuid4()
    return TaskRunLogsView(
        run_id=rid,
        task_key='onboarding.purge_expired',
        log_text='--- compensations (rollback LIFO) ---\nOK  undo_boot',
    )


class TaskMonitorAdminApiTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = MagicMock(pk='admin-1')
        self.repo_patcher = patch(f'{_MOD}._repo', return_value=MagicMock())
        self.repo_patcher.start()
        self.addCleanup(self.repo_patcher.stop)

    def _auth(self, request):
        force_authenticate(request, user=self.admin)
        return request

    def test_list_tasks_requires_authentication(self):
        req = self.factory.get('/api/v1/platform/task-monitor/tasks/')
        resp = MonitoredTaskListView.as_view()(req)
        self.assertEqual(resp.status_code, 401)

    def test_list_tasks_returns_items(self):
        req = self._auth(self.factory.get(
            '/api/v1/platform/task-monitor/tasks/?search=purge&group=onboarding',
        ))
        with patch(f'{_MOD}.ListMonitoredTasksUseCase') as UC:
            UC.return_value.execute.return_value = [_card()]
            resp = MonitoredTaskListView.as_view()(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['total'], 1)
        self.assertEqual(resp.data['data']['items'][0]['key'], 'onboarding.purge_expired')
        UC.return_value.execute.assert_called_once_with(
            search='purge', status='', group='onboarding',
        )

    def test_list_runs_paginates_and_forwards_filters(self):
        req = self._auth(self.factory.get(
            '/api/v1/platform/task-monitor/tasks/onboarding.purge_expired/runs/'
            '?status=failed&is_retry=true&limit=10&offset=10',
        ))
        with patch(f'{_MOD}.ListTaskRunsUseCase') as UC:
            UC.return_value.execute.return_value = ([_summary()], 21)
            resp = TaskRunListView.as_view()(
                req, task_key='onboarding.purge_expired',
            )

        self.assertEqual(resp.status_code, 200)
        data = resp.data['data']
        self.assertEqual(data['total'], 21)
        self.assertEqual(data['page'], 2)
        self.assertEqual(data['page_size'], 10)
        self.assertEqual(data['total_pages'], 3)
        kwargs = UC.return_value.execute.call_args.kwargs
        self.assertEqual(kwargs['status'], 'failed')
        self.assertTrue(kwargs['is_retry'])
        self.assertEqual(kwargs['limit'], 10)
        self.assertEqual(kwargs['offset'], 10)

    def test_list_runs_clamps_limit(self):
        req = self._auth(self.factory.get(
            '/api/v1/platform/task-monitor/tasks/onboarding.purge_expired/runs/?limit=999',
        ))
        with patch(f'{_MOD}.ListTaskRunsUseCase') as UC:
            UC.return_value.execute.return_value = ([], 0)
            TaskRunListView.as_view()(req, task_key='onboarding.purge_expired')
        self.assertEqual(UC.return_value.execute.call_args.kwargs['limit'], 100)

    def test_get_run_detail(self):
        run_id = uuid4()
        req = self._auth(self.factory.get(f'/api/v1/platform/task-monitor/runs/{run_id}/'))
        with patch(f'{_MOD}.GetTaskRunUseCase') as UC:
            UC.return_value.execute.return_value = _run(run_id)
            resp = TaskRunDetailView.as_view()(req, run_id=run_id)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['data']['id'], str(run_id))
        self.assertEqual(resp.data['data']['status'], 'failed')
        UC.return_value.execute.assert_called_once_with(run_id)

    def test_get_run_logs(self):
        run_id = uuid4()
        req = self._auth(self.factory.get(
            f'/api/v1/platform/task-monitor/runs/{run_id}/logs/',
        ))
        with patch(f'{_MOD}.GetTaskRunLogsUseCase') as UC:
            UC.return_value.execute.return_value = _logs(run_id)
            resp = TaskRunLogsAPIView.as_view()(req, run_id=run_id)

        self.assertEqual(resp.status_code, 200)
        self.assertIn('compensations', resp.data['data']['log_text'])
        UC.return_value.execute.assert_called_once_with(run_id)
