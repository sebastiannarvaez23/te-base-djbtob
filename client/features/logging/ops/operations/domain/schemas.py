from datetime import datetime
from enum import Enum
from typing import Literal, Optional, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RECORD_TRACE_LIMIT = 40
RECENT_ACTIVITY_LIMIT = 15
ACTIVITY_COUNT_MAX = 10_000

MilestoneEventType = Literal[
    'dispatches.exited',
    'packing.package_closed',
    'receiving.delivery_confirmed',
    'picking.tasks_created',
    'returns.closed',
]
# Must match the partial index condition on ``warehouse_events``.
RECENT_ACTIVITY_EVENT_TYPES: tuple[str, ...] = get_args(MilestoneEventType)

# Payload key listing the other records an event touches (bulk access, moved nodes…).
RELATED_REFS_KEY = 'refs'


class TraceScope(str, Enum):
    """History of a whole warehouse surface instead of a single record."""

    FLOOR_PLAN = 'floor_plan'
    TOPOLOGY = 'topology'


TRACE_SCOPE_PREFIXES: dict[TraceScope, tuple[str, ...]] = {
    TraceScope.FLOOR_PLAN: ('layout.floor_plan_',),
    # Network edits drawn on the map; the floor plan image has its own scope.
    TraceScope.TOPOLOGY: (
        'topology.', 'layout.node', 'layout.edge_', 'layout.zone_', 'layout.block_',
    ),
}


class WarehouseEventInputSchema(BaseModel):
    event_type: str
    zone: Optional[str] = None
    location: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    payload: Optional[dict] = None
    # The tenant context has no warehouse; events of a warehouse surface pass it explicitly.
    warehouse_id: Optional[UUID] = None


class WarehouseEventRecord(BaseModel):
    """Evento persistido tal como lo entrega el repositorio."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    id: UUID
    event_type: str
    occurred_at: datetime
    zone: str = ''
    location: str = ''
    payload: Optional[dict] = None
    user_id: Optional[UUID] = None
    reference_type: str = ''
    reference_id: str = ''


class RecordTraceEntry(BaseModel):
    """Un paso de la trazabilidad, en lenguaje de operación."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    id: UUID
    event_type: str
    occurred_at: datetime
    zone: str = ''
    location: str = ''
    detail: str = ''
    actor_name: str = ''


class RecentActivityEntry(BaseModel):
    """Hito de operación para el panel del toolbar. Sin payload crudo."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    id: UUID
    event_type: MilestoneEventType
    occurred_at: datetime
    detail: str = Field(default='', max_length=250)
    reference_type: str = Field(default='', max_length=100)
    reference_id: str = Field(default='', max_length=100)
    count: Optional[int] = Field(default=None, ge=0, le=ACTIVITY_COUNT_MAX)


class WarehouseEventOutputSchema(BaseModel):
    id: str
    event_type: str
    zone: Optional[str] = None
    location: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    payload: Optional[dict] = None
    user_id: Optional[UUID] = None
    warehouse_id: Optional[UUID] = None
    request_id: str
    created_at: str

    model_config = {'from_attributes': True}
