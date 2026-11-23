from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from django.utils import timezone

from platform.features.support.ops.task_monitor.domain.catalog import get_task_def
from platform.features.support.ops.task_monitor.domain.interfaces import ITaskRunRepository
from platform.features.support.ops.task_monitor.domain.schemas import (
    TaskRunLogsView,
    TaskRunSummaryView,
    TaskRunView,
    TaskStepRunView,
)
from platform.features.support.ops.task_monitor.models import (
    AutomatedTaskRun,
    AutomatedTaskStepRun,
)


def _enrich_step(step: AutomatedTaskStepRun, task_key: str) -> TaskStepRunView:
    label = ''
    icon = ''
    task_def = get_task_def(task_key)
    if task_def:
        step_def = task_def.step(step.step_key)
        if step_def:
            label = step_def.label
            icon = step_def.icon
    return TaskStepRunView(
        id=step.id,
        step_key=step.step_key,
        order=step.order,
        status=step.status,
        started_at=step.started_at,
        finished_at=step.finished_at,
        message=step.message or '',
        error_detail=step.error_detail or '',
        label=label,
        icon=icon,
    )


def _to_summary(obj: AutomatedTaskRun) -> TaskRunSummaryView:
    return TaskRunSummaryView(
        id=obj.id,
        task_key=obj.task_key,
        celery_task_id=obj.celery_task_id,
        status=obj.status,
        is_retry=obj.is_retry,
        retry_count=obj.retry_count,
        trigger=obj.trigger,
        started_at=obj.started_at,
        finished_at=obj.finished_at,
        error_summary=obj.error_summary or '',
    )


def _to_run_view(obj: AutomatedTaskRun) -> TaskRunView:
    steps = [
        _enrich_step(s, obj.task_key)
        for s in obj.steps.all().order_by('order', 'started_at')
    ]
    return TaskRunView(
        id=obj.id,
        task_key=obj.task_key,
        celery_task_id=obj.celery_task_id,
        status=obj.status,
        is_retry=obj.is_retry,
        retry_count=obj.retry_count,
        trigger=obj.trigger,
        started_at=obj.started_at,
        finished_at=obj.finished_at,
        error_summary=obj.error_summary or '',
        steps=steps,
    )


class DjangoTaskRunRepository(ITaskRunRepository):

    def create_run(
        self,
        *,
        task_key: str,
        celery_task_id: Optional[str],
        is_retry: bool,
        retry_count: int,
        trigger: str,
    ) -> TaskRunView:
        obj = AutomatedTaskRun.objects.create(
            task_key=task_key,
            celery_task_id=celery_task_id or None,
            status=AutomatedTaskRun.STATUS_PENDING,
            is_retry=is_retry,
            retry_count=retry_count,
            trigger=trigger or AutomatedTaskRun.TRIGGER_BEAT,
        )
        task_def = get_task_def(task_key)
        if task_def:
            AutomatedTaskStepRun.objects.bulk_create([
                AutomatedTaskStepRun(
                    run=obj,
                    step_key=s.key,
                    order=s.order,
                    status=AutomatedTaskStepRun.STATUS_PENDING,
                )
                for s in task_def.steps
            ])
        return _to_run_view(
            AutomatedTaskRun.objects.prefetch_related('steps').get(pk=obj.pk),
        )

    def mark_run_running(self, run_id: UUID, started_at: datetime) -> TaskRunView:
        AutomatedTaskRun.objects.filter(pk=run_id).update(
            status=AutomatedTaskRun.STATUS_RUNNING,
            started_at=started_at,
        )
        return self.get_run(run_id)  # type: ignore[return-value]

    def mark_run_finished(
        self,
        run_id: UUID,
        *,
        status: str,
        finished_at: datetime,
        error_summary: str = '',
        log_text: str = '',
    ) -> TaskRunView:
        AutomatedTaskRun.objects.filter(pk=run_id).update(
            status=status,
            finished_at=finished_at,
            error_summary=error_summary or '',
            log_text=log_text or '',
        )
        return self.get_run(run_id)  # type: ignore[return-value]

    def start_step(
        self,
        run_id: UUID,
        *,
        step_key: str,
        order: int,
        started_at: datetime,
    ) -> TaskStepRunView:
        run = AutomatedTaskRun.objects.get(pk=run_id)
        step, _ = AutomatedTaskStepRun.objects.update_or_create(
            run=run,
            step_key=step_key,
            defaults={
                'order': order,
                'status': AutomatedTaskStepRun.STATUS_RUNNING,
                'started_at': started_at,
                'finished_at': None,
                'message': '',
                'error_detail': '',
            },
        )
        return _enrich_step(step, run.task_key)

    def finish_step(
        self,
        run_id: UUID,
        *,
        step_key: str,
        status: str,
        finished_at: datetime,
        message: str = '',
        error_detail: str = '',
    ) -> TaskStepRunView:
        run = AutomatedTaskRun.objects.get(pk=run_id)
        AutomatedTaskStepRun.objects.filter(run=run, step_key=step_key).update(
            status=status,
            finished_at=finished_at,
            message=message or '',
            error_detail=error_detail or '',
        )
        step = AutomatedTaskStepRun.objects.get(run=run, step_key=step_key)
        return _enrich_step(step, run.task_key)

    def get_run(self, run_id: UUID) -> Optional[TaskRunView]:
        try:
            obj = AutomatedTaskRun.objects.prefetch_related('steps').get(pk=run_id)
        except AutomatedTaskRun.DoesNotExist:
            return None
        return _to_run_view(obj)

    def get_run_logs(self, run_id: UUID) -> Optional[TaskRunLogsView]:
        try:
            obj = AutomatedTaskRun.objects.only(
                'id', 'task_key', 'log_text',
            ).get(pk=run_id)
        except AutomatedTaskRun.DoesNotExist:
            return None
        return TaskRunLogsView(
            run_id=obj.id,
            task_key=obj.task_key,
            log_text=obj.log_text or '',
        )

    def _filter_qs(
        self,
        task_key: str,
        *,
        status: Optional[str] = None,
        is_retry: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ):
        qs = AutomatedTaskRun.objects.filter(task_key=task_key)
        if status:
            qs = qs.filter(status=status)
        if is_retry is not None:
            qs = qs.filter(is_retry=is_retry)
        if from_date:
            qs = qs.filter(started_at__gte=from_date)
        if to_date:
            qs = qs.filter(started_at__lte=to_date)
        return qs

    def list_runs(
        self,
        task_key: str,
        *,
        status: Optional[str] = None,
        is_retry: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskRunSummaryView]:
        qs = self._filter_qs(
            task_key,
            status=status,
            is_retry=is_retry,
            from_date=from_date,
            to_date=to_date,
        )
        return [_to_summary(o) for o in qs[offset:offset + limit]]

    def count_runs(
        self,
        task_key: str,
        *,
        status: Optional[str] = None,
        is_retry: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> int:
        return self._filter_qs(
            task_key,
            status=status,
            is_retry=is_retry,
            from_date=from_date,
            to_date=to_date,
        ).count()

    def latest_run(self, task_key: str) -> Optional[TaskRunSummaryView]:
        obj = (
            AutomatedTaskRun.objects
            .filter(task_key=task_key)
            .order_by('-started_at', '-created_at')
            .first()
        )
        return _to_summary(obj) if obj else None

    def count_recent_by_status(
        self, task_key: str, status: str, *, days: int = 7,
    ) -> int:
        since = timezone.now() - timedelta(days=days)
        return AutomatedTaskRun.objects.filter(
            task_key=task_key,
            status=status,
            started_at__gte=since,
        ).count()

    def has_running(self, task_key: str) -> bool:
        return AutomatedTaskRun.objects.filter(
            task_key=task_key,
            status=AutomatedTaskRun.STATUS_RUNNING,
        ).exists()
