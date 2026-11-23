from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class LiveLogLineView(BaseModel):
    id: str
    ts: datetime
    channel: str
    level: str
    logger: str
    message: str
    trace_id: str = '-'
    session_id: Optional[str] = None
    username: Optional[str] = None
    user_id: Optional[str] = None
    schema_name: Optional[str] = None
    error_code: Optional[str] = None


class LiveLogChannelView(BaseModel):
    key: str
    label: str
    icon: str
    description: str
    logger: str


class LiveLogChannelsResult(BaseModel):
    items: list[LiveLogChannelView] = Field(default_factory=list)
    levels: list[str] = Field(default_factory=list)


class LiveLogRecentResult(BaseModel):
    items: list[LiveLogLineView] = Field(default_factory=list)
    returned: int = 0
