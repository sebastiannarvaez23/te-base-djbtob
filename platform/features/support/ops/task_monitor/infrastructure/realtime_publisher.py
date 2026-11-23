"""Realtime publisher for automated-task monitor events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from core.realtime import RealtimeMessage, RealtimePublisherFactory
from core.realtime.groups import RealtimeGroups


class TaskMonitorRealtimePublisher:
    """Pushes run/step lifecycle events to the admin task-monitor group."""

    def __init__(self, publisher=None):
        self._publisher = publisher or RealtimePublisherFactory.create()

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._publisher.to_group(
            RealtimeGroups.platform_task_monitor(),
            RealtimeMessage(type=event_type, payload=payload),
        )

    def run_started(self, run) -> None:
        self.emit('task_run.started', self._run_payload(run))

    def run_finished(self, run) -> None:
        self.emit('task_run.finished', self._run_payload(run))

    def step_started(self, run, step) -> None:
        self.emit('task_step.started', self._step_payload(run, step))

    def step_succeeded(self, run, step) -> None:
        self.emit('task_step.succeeded', self._step_payload(run, step))

    def step_failed(self, run, step) -> None:
        self.emit('task_step.failed', self._step_payload(run, step))

    @staticmethod
    def _run_payload(run) -> dict[str, Any]:
        return {
            'run_id': str(run.id),
            'task_key': run.task_key,
            'celery_task_id': run.celery_task_id,
            'status': run.status,
            'is_retry': run.is_retry,
            'retry_count': run.retry_count,
            'trigger': run.trigger,
            'started_at': run.started_at.isoformat() if run.started_at else None,
            'finished_at': run.finished_at.isoformat() if run.finished_at else None,
            'error_summary': run.error_summary or '',
        }

    @staticmethod
    def _step_payload(run, step) -> dict[str, Any]:
        return {
            'run_id': str(run.id),
            'task_key': run.task_key,
            'step_key': step.step_key,
            'order': step.order,
            'status': step.status,
            'is_retry': run.is_retry,
            'retry_count': run.retry_count,
            'started_at': step.started_at.isoformat() if step.started_at else None,
            'finished_at': step.finished_at.isoformat() if step.finished_at else None,
            'message': step.message or '',
            'error_detail': step.error_detail or '',
        }
