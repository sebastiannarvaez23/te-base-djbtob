from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentRunListItemSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: UUID
    tenant_schema: str
    user_id: UUID
    conversation_id: Optional[UUID] = None
    status: str
    provider: str = ''
    model_id: str = ''
    degraded: bool = False
    cancel_requested: bool = False
    step_count: int = 0
    error_code: str = ''
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AgentRunListResultSchema(BaseModel):
    """
    ``total`` is the size of the **sampled** corpus (capped probe), not a
    global count across all tenants/history.
    """

    items: list[AgentRunListItemSchema] = Field(default_factory=list)
    total: int = 0
    page: int = 0
    page_size: int = 20
    sampled: bool = True
    max_tenants: int = 50
    per_tenant_limit: int = 20
