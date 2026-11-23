"""Contratos Pydantic del harness (tipado estricto, agnóstico de producto)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.ids import uuid7

AgentRunStatus = Literal[
    'queued',
    'running',
    'awaiting_approval',
    'streaming',
    'completed',
    'cancelled',
    'failed',
    'degraded',
]


class LoopConfig(BaseModel):
    """Límites operativos del bucle (inyectados desde policy de producto)."""

    max_steps: int = Field(default=4, ge=1, le=32)
    history_turns: int = Field(default=8, ge=1, le=64)
    require_tool_before_facts: bool = True
    out_of_scope_message: str = ''


class AgentRunSchema(BaseModel):
    """Snapshot de un AgentRun (persistido en schema tenant)."""

    model_config = ConfigDict(protected_namespaces=())

    id: uuid.UUID = Field(default_factory=uuid7)
    conversation_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    status: AgentRunStatus = 'queued'
    provider: str = 'fake'
    model_id: str = ''
    degraded: bool = False
    cancel_requested: bool = False
    step_count: int = 0
    error_code: str = ''
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
