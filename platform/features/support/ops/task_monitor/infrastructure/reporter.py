"""Concrete ITaskProgressReporter: persist runs/steps and emit WS events."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from platform.features.support.ops.task_monitor.infrastructure.realtime_publisher import (
    TaskMonitorRealtimePublisher,
)
from platform.features.support.ops.task_monitor.infrastructure.repositories import (
    DjangoTaskRunRepository,
)
from platform.features.support.ops.task_monitor.models import (
    AutomatedTaskRun,
    AutomatedTaskStepRun,
)

logger = logging.getLogger('app.tasks')


class DjangoTaskProgressReporter:
    """Persists progress and fans out realtime events (best-effort)."""

    def __init__(self, repository=None, realtime=None, failure_notifier=None):
        self._repo = repository or DjangoTaskRunRepository()
        self._rt = realtime or TaskMonitorRealtimePublisher()
        self._failure_notifier = failure_notifier

    def start_run(
        self,
        *,
        task_key: str,
        celery_task_id: Optional[str],
        is_retry: bool,
        retry_count: int,
        trigger: str,
    ) -> UUID:
        view = self._repo.create_run(
            task_key=task_key,
            celery_task_id=celery_task_id,
            is_retry=is_retry,
            retry_count=retry_count,
            trigger=trigger,
        )
        return view.id

    def mark_running(self, run_id: UUID, started_at: datetime) -> None:
        view = self._repo.mark_run_running(run_id, started_at)
        try:
            obj = AutomatedTaskRun.objects.get(pk=run_id)
            self._rt.run_started(obj)
        except Exception:
            pass
        _ = view

    def finish_run(
        self,
        run_id: UUID,
        *,
        status: str,
        finished_at: datetime,
        error_summary: str = '',
        log_text: str = '',
    ) -> None:
        # Mark any still-pending steps as skipped when the run ends early.
        if status in (
            AutomatedTaskRun.STATUS_SKIPPED,
            AutomatedTaskRun.STATUS_FAILED,
            AutomatedTaskRun.STATUS_SUCCESS,
        ):
            AutomatedTaskStepRun.objects.filter(
                run_id=run_id,
                status=AutomatedTaskStepRun.STATUS_PENDING,
            ).update(
                status=AutomatedTaskStepRun.STATUS_SKIPPED,
                finished_at=finished_at,
            )
        self._repo.mark_run_finished(
            run_id,
            status=status,
            finished_at=finished_at,
            error_summary=error_summary,
            log_text=log_text,
        )
        obj = None
        try:
            obj = AutomatedTaskRun.objects.get(pk=run_id)
            self._rt.run_finished(obj)
        except Exception:
            pass
        if status == AutomatedTaskRun.STATUS_FAILED:
            if obj is None:
                try:
                    obj = AutomatedTaskRun.objects.get(pk=run_id)
                except Exception:
                    obj = None
            if obj is not None:
                self._notify_failure(obj)

    def start_step(
        self,
        run_id: UUID,
        *,
        step_key: str,
        order: int,
        started_at: datetime,
    ) -> None:
        # Prefer catalog/pre-seeded order when caller passes 0.
        if order <= 0:
            existing = AutomatedTaskStepRun.objects.filter(
                run_id=run_id, step_key=step_key,
            ).first()
            if existing:
                order = existing.order
        step = self._repo.start_step(
            run_id, step_key=step_key, order=order, started_at=started_at,
        )
        try:
            run = AutomatedTaskRun.objects.get(pk=run_id)
            step_obj = AutomatedTaskStepRun.objects.get(run_id=run_id, step_key=step_key)
            self._rt.step_started(run, step_obj)
        except Exception:
            pass
        _ = step

    def finish_step(
        self,
        run_id: UUID,
        *,
        step_key: str,
        status: str,
        finished_at: datetime,
        message: str = '',
        error_detail: str = '',
    ) -> None:
        step = self._repo.finish_step(
            run_id,
            step_key=step_key,
            status=status,
            finished_at=finished_at,
            message=message,
            error_detail=error_detail,
        )
        try:
            run = AutomatedTaskRun.objects.get(pk=run_id)
            step_obj = AutomatedTaskStepRun.objects.get(run_id=run_id, step_key=step_key)
            if status == AutomatedTaskStepRun.STATUS_FAILED:
                self._rt.step_failed(run, step_obj)
            else:
                self._rt.step_succeeded(run, step_obj)
        except Exception:
            pass
        _ = step

    def _notify_failure(self, run: AutomatedTaskRun) -> None:
        notifier = self._failure_notifier
        if notifier is None:
            return
        try:
            notifier.notify_failed(
                task_key=run.task_key,
                run_id=run.id,
                error_summary=run.error_summary or '',
            )
        except Exception as exc:
            logger.warning(
                'automated_task_failure_notify_failed task=%s run=%s error=%s',
                run.task_key, run.id, exc,
            )
