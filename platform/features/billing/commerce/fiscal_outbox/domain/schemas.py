from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FiscalOutboxKind(str, Enum):
    ISSUE = 'issue'
    VOID = 'void'


class FiscalOutboxStatus(str, Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    DONE = 'done'
    DEAD = 'dead'


class FiscalDeadReason(str, Enum):
    NONE = ''
    REJECTED = 'rejected'
    EXPIRED = 'expired'


class FiscalOutboxEventSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: FiscalOutboxKind
    invoice_id: UUID
    charge_id: Optional[UUID] = None
    idempotency_key: str
    reason: str = ''
    trace_id: str = ''
    status: FiscalOutboxStatus
    attempts: int = 0
    next_attempt_at: datetime
    last_error: str = ''
    last_error_code: str = ''
    dead_reason: FiscalDeadReason = FiscalDeadReason.NONE
    created_at: datetime


class EnqueueFiscalOutboxSchema(BaseModel):
    model_config = ConfigDict(extra='forbid')

    kind: FiscalOutboxKind
    invoice_id: UUID
    charge_id: Optional[UUID] = None
    idempotency_key: str = Field(min_length=1, max_length=120)
    reason: str = Field(default='', max_length=200)
    trace_id: str = Field(default='', max_length=64)


class FiscalBacklogSchema(BaseModel):
    count: int = 0
    oldest_created_at: Optional[datetime] = None


class RelayResultSchema(BaseModel):
    claimed: int = 0
    done: int = 0
    retried: int = 0
    deferred: int = 0
    dead: int = 0
    circuit_open: bool = False
