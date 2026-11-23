"""Pydantic contracts for predictive ML ports (cubo 3)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class DemandForecastPoint(BaseModel):
    period_start: date
    quantity: Decimal
    lower: Optional[Decimal] = None
    upper: Optional[Decimal] = None


class DemandForecastRequest(BaseModel):
    sku_id: str
    warehouse_id: Optional[str] = None
    horizon_days: int = 30
    history: List[DemandForecastPoint] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class DemandForecastResult(BaseModel):
    model_config = {'protected_namespaces': ()}

    sku_id: str
    points: List[DemandForecastPoint] = Field(default_factory=list)
    model_version: str = ''
    provider: str = ''
    latency_ms: int = 0
    degraded: bool = False


class AnomalySignal(BaseModel):
    entity_type: str
    entity_id: str
    score: float
    reason: str = ''
    observed_at: Optional[str] = None


class AnomalyDetectionRequest(BaseModel):
    scope: str = 'inventory'
    entity_ids: List[str] = Field(default_factory=list)
    features: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class AnomalyDetectionResult(BaseModel):
    model_config = {'protected_namespaces': ()}

    signals: List[AnomalySignal] = Field(default_factory=list)
    model_version: str = ''
    provider: str = ''
    latency_ms: int = 0
    degraded: bool = False
