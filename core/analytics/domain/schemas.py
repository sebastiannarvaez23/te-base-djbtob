"""Schemas Pydantic del dominio analytics / ETL."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from core.ids import uuid7

from .enums import LoadMode, PipelineKey, RunStatus, Trigger, WatermarkStrategy


class Watermark(BaseModel):
    strategy: WatermarkStrategy = WatermarkStrategy.TIMESTAMP
    cursor_ts: Optional[datetime] = None
    cursor_id: Optional[str] = None
    cursor_opaque: Optional[str] = None


class PipelineContext(BaseModel):
    """Contexto de una corrida ETL por tenant."""

    company_id: UUID
    schema_name: str = Field(min_length=1, max_length=63)
    pipeline_key: str = Field(min_length=1, max_length=64)
    trigger: Trigger = Trigger.MANUAL
    run_id: UUID = Field(default_factory=uuid7)
    watermark: Optional[Watermark] = None
    dry_run: bool = False
    extras: dict[str, Any] = Field(default_factory=dict)

    @field_validator('pipeline_key', mode='before')
    @classmethod
    def _coerce_pipeline_key(cls, value: Any) -> str:
        if isinstance(value, PipelineKey):
            return value.value
        return str(value)


class StepMetric(BaseModel):
    step: str
    rows: int = 0
    duration_ms: int = 0
    ok: bool = True
    error: Optional[str] = None


class PipelineResult(BaseModel):
    status: RunStatus
    pipeline_key: str
    company_id: UUID
    run_id: UUID
    rows_extracted: int = 0
    rows_staged: int = 0
    rows_transformed: int = 0
    rows_loaded: int = 0
    watermark_before: Optional[Watermark] = None
    watermark_after: Optional[Watermark] = None
    duration_ms: int = 0
    error: Optional[str] = None
    steps: list[StepMetric] = Field(default_factory=list)


class AnalyticsQuery(BaseModel):
    """Lectura tipada desde el mart. ``company_id`` es obligatorio."""

    company_id: UUID
    dataset: str = Field(min_length=1, max_length=128)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=1000, ge=1, le=10_000)
    offset: int = Field(default=0, ge=0)


class AnalyticsResult(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class TransformPlan(BaseModel):
    """Plan ELT futuro; en ETL MVP no se usa en caliente."""

    name: str
    sql: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)


class TransformResult(BaseModel):
    rows_affected: int = 0
    detail: str = ''


class LoadTarget(BaseModel):
    """Destino de publicación del mart tras transform."""

    mode: LoadMode = LoadMode.NOOP
    name: str = ''
    merge_keys: list[str] = Field(default_factory=list)


class ExtractBatch(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    next_watermark: Optional[Watermark] = None


class TransformBatch(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    target: LoadTarget = Field(default_factory=LoadTarget)
