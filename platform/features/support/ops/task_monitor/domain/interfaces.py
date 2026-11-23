from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from platform.features.support.ops.task_monitor.domain.schemas import (
    TaskRunLogsView,
    TaskRunSummaryView,
    TaskRunView,
    TaskStepRunView,
)


class ITaskRunRepository(ABC):

    @abstractmethod
    def create_run(
        self,
        *,
        task_key: str,
        celery_task_id: Optional[str],
        is_retry: bool,
        retry_count: int,
        trigger: str,
    ) -> TaskRunView:
        ...

    @abstractmethod
    def mark_run_running(self, run_id: UUID, started_at: datetime) -> TaskRunView:
        ...

    @abstractmethod
    def mark_run_finished(
        self,
        run_id: UUID,
        *,
        status: str,
        finished_at: datetime,
        error_summary: str = '',
        log_text: str = '',
    ) -> TaskRunView:
        ...

    @abstractmethod
    def start_step(
        self,
        run_id: UUID,
        *,
        step_key: str,
        order: int,
        started_at: datetime,
    ) -> TaskStepRunView:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def get_run(self, run_id: UUID) -> Optional[TaskRunView]:
        ...

    @abstractmethod
    def get_run_logs(self, run_id: UUID) -> Optional[TaskRunLogsView]:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def count_runs(
        self,
        task_key: str,
        *,
        status: Optional[str] = None,
        is_retry: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> int:
        ...

    @abstractmethod
    def latest_run(self, task_key: str) -> Optional[TaskRunSummaryView]:
        ...

    @abstractmethod
    def count_recent_by_status(
        self, task_key: str, status: str, *, days: int = 7,
    ) -> int:
        ...

    @abstractmethod
    def has_running(self, task_key: str) -> bool:
        ...
