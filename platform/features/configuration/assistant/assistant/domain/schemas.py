from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from core.ai.assistant_catalog import (
    ASSISTANT_HISTORY_MAX,
    ASSISTANT_HISTORY_MIN,
    ASSISTANT_MAX_MESSAGE_MAX,
    ASSISTANT_MAX_MESSAGE_MIN,
    ASSISTANT_OUT_OF_SCOPE_MAX,
    ASSISTANT_PROVIDERS,
    ASSISTANT_STEPS_MAX,
    ASSISTANT_STEPS_MIN,
    ASSISTANT_TOOL_KEYS,
)

RuntimeHealth = Literal['ok', 'down', 'unknown']


class AssistantToolToggleSchema(BaseModel):
    key: str
    enabled: bool = True

    @field_validator('key')
    @classmethod
    def known_tool(cls, value: str) -> str:
        key = (value or '').strip()
        if key not in ASSISTANT_TOOL_KEYS:
            raise ValueError(f'Unknown assistant tool: {key}')
        return key


class AssistantUsageSchema(BaseModel):
    messages_24h: int = 0
    conversations_24h: int = 0
    quota_hits_24h: int = 0
    errors_24h: int = 0


class AssistantSettingsPersistSchema(BaseModel):
    enabled: bool = True
    provider: str = 'local'
    max_message_chars: int = 4000
    max_agent_steps: int = 4
    history_turns: int = 8
    out_of_scope_message: str = ''
    require_tool_before_facts: bool = True
    enabled_tools: dict[str, bool] = Field(default_factory=dict)

    @field_validator('provider')
    @classmethod
    def provider_ok(cls, value: str) -> str:
        name = (value or '').lower()
        if name not in ASSISTANT_PROVIDERS:
            raise ValueError(f'Invalid provider: {value}')
        return name

    @field_validator('max_message_chars')
    @classmethod
    def chars_range(cls, value: int) -> int:
        if not (ASSISTANT_MAX_MESSAGE_MIN <= value <= ASSISTANT_MAX_MESSAGE_MAX):
            raise ValueError('max_message_chars out of range')
        return value

    @field_validator('max_agent_steps')
    @classmethod
    def steps_range(cls, value: int) -> int:
        if not (ASSISTANT_STEPS_MIN <= value <= ASSISTANT_STEPS_MAX):
            raise ValueError('max_agent_steps out of range')
        return value

    @field_validator('history_turns')
    @classmethod
    def history_range(cls, value: int) -> int:
        if not (ASSISTANT_HISTORY_MIN <= value <= ASSISTANT_HISTORY_MAX):
            raise ValueError('history_turns out of range')
        return value

    @field_validator('out_of_scope_message')
    @classmethod
    def scope_len(cls, value: str) -> str:
        text = value or ''
        if len(text) > ASSISTANT_OUT_OF_SCOPE_MAX:
            raise ValueError('out_of_scope_message too long')
        return text


class AssistantAdminSettingsSchema(BaseModel):
    id: Optional[UUID] = None
    enabled: bool
    provider: str
    max_message_chars: int
    max_agent_steps: int
    history_turns: int
    out_of_scope_message: str
    require_tool_before_facts: bool
    tools: list[AssistantToolToggleSchema]
    runtime_health: RuntimeHealth = 'unknown'
    usage: AssistantUsageSchema = Field(default_factory=AssistantUsageSchema)
    updated_at: Optional[datetime] = None
