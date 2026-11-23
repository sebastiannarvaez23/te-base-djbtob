from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStepDefView(BaseModel):
    key: str
    label: str
    icon: str
    order: int


class TaskStepRunView(BaseModel):
    id: UUID
    step_key: str
    order: int
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    message: str = ''
    error_detail: str = ''
    label: str = ''
    icon: str = ''


class TaskRunView(BaseModel):
    id: UUID
    task_key: str
    celery_task_id: Optional[str] = None
    status: str
    is_retry: bool = False
    retry_count: int = 0
    trigger: str = 'beat'
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_summary: str = ''
    steps: list[TaskStepRunView] = Field(default_factory=list)


class TaskRunSummaryView(BaseModel):
    id: UUID
    task_key: str
    celery_task_id: Optional[str] = None
    status: str
    is_retry: bool = False
    retry_count: int = 0
    trigger: str = 'beat'
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_summary: str = ''


class TaskCardView(BaseModel):
    key: str
    title: str
    description: str
    icon: str
    schedule_label: str
    group: str
    steps: list[TaskStepDefView]
    last_run: Optional[TaskRunSummaryView] = None
    recent_success_count: int = 0
    recent_failed_count: int = 0
    is_running: bool = False


class TaskRunLogsView(BaseModel):
    run_id: UUID
    task_key: str
    log_text: str = ''
