"""Schemas del dominio assistant."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AgentAction(BaseModel):
    """Acción parseada de la salida del SLM (JSON estricto)."""

    action: Literal['tool', 'final']
    name: Optional[str] = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    text: Optional[str] = None


class ToolCallAuditSchema(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error_code: str = ''
    result_preview: str = ''


class ChatMessageSchema(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class ChatTurnResultSchema(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    degraded: bool = False
    tools_used: list[ToolCallAuditSchema] = Field(default_factory=list)
    messages: list[ChatMessageSchema] = Field(default_factory=list)


class ConversationSummarySchema(BaseModel):
    id: uuid.UUID
    title: str
    updated_at: datetime
    message_count: int = 0


class AssistantStatusSchema(BaseModel):
    enabled: bool
    provider: str = 'fake'
