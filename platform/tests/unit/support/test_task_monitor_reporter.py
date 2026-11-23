"""Unit tests for task-monitor repository pre-seed + progress reporter."""

from __future__ import annotations

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from platform.features.support.ops.task_monitor.domain.catalog import get_task_def
from platform.features.support.ops.task_monitor.domain.schemas import (
    TaskRunView,
    TaskStepRunView,
)
from platform.features.support.ops.task_monitor.infrastructure.reporter import (
    DjangoTaskProgressReporter,
)
from platform.features.support.ops.task_monitor.infrastructure.repositories import (
    DjangoTaskRunRepository,
)
from platform.features.support.ops.task_monitor.models import (
    AutomatedTaskRun,
    AutomatedTaskStepRun,
)

pytestmark = pytest.mark.unit

_REPO_MOD = 'platform.features.support.ops.task_monitor.infrastructure.repositories'
_REP_MOD = 'platform.features.support.ops.task_monitor.infrastructure.reporter'


_CATALOG_TASK = 'onboarding.purge_expired'


def _now():
    return datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def _run_view(run_id, task_key=_CATALOG_TASK, steps=None):
    return TaskRunView(
        id=run_id,
        task_key=task_key,
        celery_task_id='celery-1',
        status='pending',
        steps=steps or [],
    )


def _step_view(step_key='boot', order=1, status='running'):
    return TaskStepRunView(
        id=uuid4(),
        step_key=step_key,
        order=order,
        status=status,
    )


class DjangoTaskRunRepositoryPreseedTests(TestCase):
    """ORM create/bulk_create is mocked — no real DB required."""

    @patch(f'{_REPO_MOD}._to_run_view')
    @patch(f'{_REPO_MOD}.AutomatedTaskRun.objects')
    @patch(f'{_REPO_MOD}.AutomatedTaskStepRun.objects')
    def test_create_run_preseeds_catalog_steps(
        self, mock_step_objects, mock_run_objects, mock_to_view,
    ):
        run_id = uuid4()
        created = AutomatedTaskRun(
            id=run_id,
            task_key=_CATALOG_TASK,
            celery_task_id='c-1',
            status=AutomatedTaskRun.STATUS_PENDING,
            is_retry=False,
            retry_count=0,
            trigger='beat',
        )
        mock_run_objects.create.return_value = created
        mock_run_objects.prefetch_related.return_value.get.return_value = created
        mock_to_view.return_value = _run_view(run_id)

        view = DjangoTaskRunRepository().create_run(
            task_key=_CATALOG_TASK,
            celery_task_id='c-1',
            is_retry=False,
            retry_count=0,
            trigger='beat',
        )

        self.assertEqual(view.id, run_id)
        mock_step_objects.bulk_create.assert_called_once()
        seeded = mock_step_objects.bulk_create.call_args[0][0]
        catalog = get_task_def(_CATALOG_TASK)
        assert catalog is not None
        self.assertEqual([s.step_key for s in seeded], [s.key for s in catalog.steps])
        self.assertEqual([s.order for s in seeded], [s.order for s in catalog.steps])
        self.assertTrue(all(
            s.status == AutomatedTaskStepRun.STATUS_PENDING for s in seeded
        ))

    @patch(f'{_REPO_MOD}._to_run_view')
    @patch(f'{_REPO_MOD}.AutomatedTaskRun.objects')
    @patch(f'{_REPO_MOD}.AutomatedTaskStepRun.objects')
    def test_create_run_unknown_task_skips_preseed(
        self, mock_step_objects, mock_run_objects, mock_to_view,
    ):
        run_id = uuid4()
        created = AutomatedTaskRun(
            id=run_id,
            task_key='unknown.task',
            status=AutomatedTaskRun.STATUS_PENDING,
            trigger='manual',
        )
        mock_run_objects.create.return_value = created
        mock_run_objects.prefetch_related.return_value.get.return_value = created
        mock_to_view.return_value = _run_view(run_id, task_key='unknown.task')

        DjangoTaskRunRepository().create_run(
            task_key='unknown.task',
            celery_task_id=None,
            is_retry=False,
            retry_count=0,
            trigger='manual',
        )
        mock_step_objects.bulk_create.assert_not_called()


class DjangoTaskProgressReporterTests(TestCase):

    def setUp(self):
        self.repo = MagicMock()
        self.rt = MagicMock()
        self.reporter = DjangoTaskProgressReporter(repository=self.repo, realtime=self.rt)
        self.run_id = uuid4()
        self.repo.create_run.return_value = _run_view(self.run_id)
        self.repo.mark_run_running.return_value = _run_view(self.run_id)
        self.repo.mark_run_finished.return_value = _run_view(self.run_id)
        self.repo.start_step.return_value = _step_view()
        self.repo.finish_step.return_value = _step_view(status='success')

    def test_start_run_delegates_to_repository(self):
        rid = self.reporter.start_run(
            task_key=_CATALOG_TASK,
            celery_task_id='c1',
            is_retry=True,
            retry_count=2,
            trigger='beat',
        )
        self.assertEqual(rid, self.run_id)
        self.repo.create_run.assert_called_once_with(
            task_key=_CATALOG_TASK,
            celery_task_id='c1',
            is_retry=True,
            retry_count=2,
            trigger='beat',
        )

    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_mark_running_emits_realtime(self, mock_runs):
        obj = MagicMock()
        mock_runs.get.return_value = obj
        self.reporter.mark_running(self.run_id, _now())
        self.repo.mark_run_running.assert_called_once_with(self.run_id, _now())
        self.rt.run_started.assert_called_once_with(obj)

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_finish_run_skips_pending_steps_then_persists(self, mock_runs, mock_steps):
        mock_runs.get.return_value = MagicMock()
        pending_qs = MagicMock()
        mock_steps.filter.return_value = pending_qs

        self.reporter.finish_run(
            self.run_id,
            status=AutomatedTaskRun.STATUS_FAILED,
            finished_at=_now(),
            error_summary='boom',
            log_text='--- compensations ---',
        )

        mock_steps.filter.assert_called_once_with(
            run_id=self.run_id,
            status=AutomatedTaskStepRun.STATUS_PENDING,
        )
        pending_qs.update.assert_called_once()
        self.repo.mark_run_finished.assert_called_once()
        self.rt.run_finished.assert_called_once()

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_start_step_uses_preseeded_order_when_zero(self, mock_runs, mock_steps):
        existing = MagicMock(order=3)
        mock_steps.filter.return_value.first.return_value = existing
        mock_runs.get.return_value = MagicMock()
        mock_steps.get.return_value = MagicMock()

        self.reporter.start_step(
            self.run_id, step_key='work', order=0, started_at=_now(),
        )
        self.repo.start_step.assert_called_once()
        self.assertEqual(self.repo.start_step.call_args.kwargs['order'], 3)
        self.rt.step_started.assert_called_once()

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_finish_step_failed_emits_step_failed(self, mock_runs, mock_steps):
        mock_runs.get.return_value = MagicMock()
        mock_steps.get.return_value = MagicMock()
        self.reporter.finish_step(
            self.run_id,
            step_key='work',
            status=AutomatedTaskStepRun.STATUS_FAILED,
            finished_at=_now(),
            error_detail='x',
        )
        self.rt.step_failed.assert_called_once()
        self.rt.step_succeeded.assert_not_called()

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_realtime_failures_are_swallowed(self, mock_runs, mock_steps):
        mock_runs.get.side_effect = RuntimeError('ws down')
        mock_steps.filter.return_value = MagicMock()
        # Must not raise
        self.reporter.mark_running(self.run_id, _now())
        self.reporter.finish_run(
            self.run_id,
            status=AutomatedTaskRun.STATUS_SUCCESS,
            finished_at=_now(),
        )

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_finish_run_failed_notifies_inbox(self, mock_runs, mock_steps):
        notifier = MagicMock()
        self.reporter = DjangoTaskProgressReporter(
            repository=self.repo, realtime=self.rt, failure_notifier=notifier,
        )
        obj = MagicMock(id=self.run_id, task_key=_CATALOG_TASK, error_summary='boom')
        mock_runs.get.return_value = obj
        mock_steps.filter.return_value = MagicMock()

        self.reporter.finish_run(
            self.run_id,
            status=AutomatedTaskRun.STATUS_FAILED,
            finished_at=_now(),
            error_summary='boom',
        )

        notifier.notify_failed.assert_called_once_with(
            task_key=_CATALOG_TASK,
            run_id=self.run_id,
            error_summary='boom',
        )

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_finish_run_success_does_not_notify(self, mock_runs, mock_steps):
        notifier = MagicMock()
        self.reporter = DjangoTaskProgressReporter(
            repository=self.repo, realtime=self.rt, failure_notifier=notifier,
        )
        mock_runs.get.return_value = MagicMock()
        mock_steps.filter.return_value = MagicMock()

        self.reporter.finish_run(
            self.run_id,
            status=AutomatedTaskRun.STATUS_SUCCESS,
            finished_at=_now(),
        )
        notifier.notify_failed.assert_not_called()

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_finish_run_skipped_does_not_notify(self, mock_runs, mock_steps):
        notifier = MagicMock()
        self.reporter = DjangoTaskProgressReporter(
            repository=self.repo, realtime=self.rt, failure_notifier=notifier,
        )
        mock_runs.get.return_value = MagicMock()
        mock_steps.filter.return_value = MagicMock()

        self.reporter.finish_run(
            self.run_id,
            status=AutomatedTaskRun.STATUS_SKIPPED,
            finished_at=_now(),
        )
        notifier.notify_failed.assert_not_called()

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_finish_run_still_notifies_when_realtime_fails(self, mock_runs, mock_steps):
        notifier = MagicMock()
        self.reporter = DjangoTaskProgressReporter(
            repository=self.repo, realtime=self.rt, failure_notifier=notifier,
        )
        obj = MagicMock(id=self.run_id, task_key=_CATALOG_TASK, error_summary='')
        mock_runs.get.side_effect = [RuntimeError('ws down'), obj]
        mock_steps.filter.return_value = MagicMock()

        self.reporter.finish_run(
            self.run_id,
            status=AutomatedTaskRun.STATUS_FAILED,
            finished_at=_now(),
        )
        notifier.notify_failed.assert_called_once()

    @patch(f'{_REP_MOD}.AutomatedTaskStepRun.objects')
    @patch(f'{_REP_MOD}.AutomatedTaskRun.objects')
    def test_finish_run_swallows_notifier_errors(self, mock_runs, mock_steps):
        notifier = MagicMock()
        notifier.notify_failed.side_effect = RuntimeError('inbox down')
        self.reporter = DjangoTaskProgressReporter(
            repository=self.repo, realtime=self.rt, failure_notifier=notifier,
        )
        mock_runs.get.return_value = MagicMock(
            id=self.run_id, task_key=_CATALOG_TASK, error_summary='x',
        )
        mock_steps.filter.return_value = MagicMock()

        self.reporter.finish_run(
            self.run_id,
            status=AutomatedTaskRun.STATUS_FAILED,
            finished_at=_now(),
        )
