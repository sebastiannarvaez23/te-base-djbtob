"""Application use cases for the admin automated-task monitor."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from core.errors import AppErrorCode, NotFoundException
from platform.features.support.ops.task_monitor.domain.catalog import (
    get_task_def,
    list_task_defs,
)
from platform.features.support.ops.task_monitor.domain.interfaces import ITaskRunRepository
from platform.features.support.ops.task_monitor.domain.schemas import (
    TaskCardView,
    TaskRunLogsView,
    TaskRunSummaryView,
    TaskRunView,
    TaskStepDefView,
)
from platform.features.support.ops.task_monitor.models import AutomatedTaskRun
from core.trace import trace_layer


class ListMonitoredTasksUseCase:
    def __init__(self, repository: ITaskRunRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        *,
        search: str = '',
        status: str = '',
        group: str = '',
    ) -> list[TaskCardView]:
        cards: list[TaskCardView] = []
        needle = (search or '').strip().lower()
        for task in list_task_defs():
            if group and task.group != group:
                continue
            if needle and needle not in task.key.lower() and needle not in task.title.lower():
                continue
            last = self.repository.latest_run(task.key)
            if status and (not last or last.status != status):
                continue
            cards.append(TaskCardView(
                key=task.key,
                title=task.title,
                description=task.description,
                icon=task.icon,
                schedule_label=task.schedule_label,
                group=task.group,
                steps=[
                    TaskStepDefView(
                        key=s.key, label=s.label, icon=s.icon, order=s.order,
                    )
                    for s in task.steps
                ],
                last_run=last,
                recent_success_count=self.repository.count_recent_by_status(
                    task.key, AutomatedTaskRun.STATUS_SUCCESS,
                ),
                recent_failed_count=self.repository.count_recent_by_status(
                    task.key, AutomatedTaskRun.STATUS_FAILED,
                ),
                is_running=self.repository.has_running(task.key),
            ))
        return cards


class ListTaskRunsUseCase:
    def __init__(self, repository: ITaskRunRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self,
        task_key: str,
        *,
        status: Optional[str] = None,
        is_retry: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TaskRunSummaryView], int]:
        if get_task_def(task_key) is None:
            raise NotFoundException(AppErrorCode.TASKMON_TASK_NOT_FOUND)
        items = self.repository.list_runs(
            task_key,
            status=status,
            is_retry=is_retry,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        total = self.repository.count_runs(
            task_key,
            status=status,
            is_retry=is_retry,
            from_date=from_date,
            to_date=to_date,
        )
        return items, total


class GetTaskRunUseCase:
    def __init__(self, repository: ITaskRunRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, run_id: UUID) -> TaskRunView:
        run = self.repository.get_run(run_id)
        if run is None:
            raise NotFoundException(AppErrorCode.TASKMON_RUN_NOT_FOUND)
        return run


class GetTaskRunLogsUseCase:
    def __init__(self, repository: ITaskRunRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, run_id: UUID) -> TaskRunLogsView:
        logs = self.repository.get_run_logs(run_id)
        if logs is None:
            raise NotFoundException(AppErrorCode.TASKMON_RUN_NOT_FOUND)
        return logs
