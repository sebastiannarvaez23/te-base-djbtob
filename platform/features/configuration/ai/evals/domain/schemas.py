from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EvalCaseOutSchema(BaseModel):
    key: str
    description: str
    passed: bool
    detail: str = ''


class EvalSuiteOutSchema(BaseModel):
    id: UUID
    suite: str
    passed: int
    failed: int
    cases: list[EvalCaseOutSchema] = Field(default_factory=list)
    ran_at: datetime


class EvalSuiteListSchema(BaseModel):
    items: list[EvalSuiteOutSchema] = Field(default_factory=list)
    total: int = 0
    page: int = 0
    page_size: int = 20
    latest: Optional[EvalSuiteOutSchema] = None
