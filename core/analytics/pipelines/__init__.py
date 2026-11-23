"""Pipelines ETL. Fase 1 solo incluye NullPipeline (smoke / tests)."""

from __future__ import annotations

from typing import Any

from core.analytics.domain.enums import LoadMode, PipelineKey
from core.analytics.domain.interfaces import IPipeline
from core.analytics.domain.schemas import ExtractBatch, LoadTarget, PipelineContext, TransformBatch


class NullPipeline(IPipeline):
    """Extract vacío → success con rows=0 (idempotencia / smoke)."""

    key = PipelineKey.NULL.value

    def extract(self, ctx: PipelineContext) -> ExtractBatch:
        return ExtractBatch(rows=[])

    def transform(self, ctx: PipelineContext, rows: list[dict[str, Any]]) -> TransformBatch:
        return TransformBatch(
            rows=rows,
            target=LoadTarget(mode=LoadMode.NOOP),
        )


def register_builtin_pipelines() -> None:
    from core.analytics.infrastructure.registry import register_pipeline

    register_pipeline(PipelineKey.NULL.value, NullPipeline)
