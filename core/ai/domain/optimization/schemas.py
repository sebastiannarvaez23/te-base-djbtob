"""Pydantic contracts for OR / optimization ports (cubo 4)."""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class RouteStop(BaseModel):
    """A stop on a picking or travel path."""

    position_id: str
    location_id: str
    sequence: int = 0
    quantity: Decimal = Decimal('0')


class PickingRouteRequest(BaseModel):
    """Input for sequencing picks inside a warehouse."""

    warehouse_id: str
    required_quantity: Decimal
    candidates: List[RouteStop] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class PickingRouteResult(BaseModel):
    """Ordered allocations returned by ``IPickingRouter``."""

    allocations: List[RouteStop] = Field(default_factory=list)
    total_quantity: Decimal = Decimal('0')
    provider: str = ''
    latency_ms: int = 0
    degraded: bool = False


class BatchOrderRef(BaseModel):
    order_id: str
    line_count: int = 0
    zone_hint: Optional[str] = None


class BatchGroupRequest(BaseModel):
    """Input for grouping orders into waves/batches."""

    warehouse_id: str
    orders: List[BatchOrderRef] = Field(default_factory=list)
    max_batch_size: int = 20
    metadata: dict = Field(default_factory=dict)


class BatchGroup(BaseModel):
    batch_id: str
    order_ids: List[str] = Field(default_factory=list)


class BatchGroupResult(BaseModel):
    batches: List[BatchGroup] = Field(default_factory=list)
    provider: str = ''
    latency_ms: int = 0
    degraded: bool = False
