"""PipelineRunner — extract → stage → transform → load con métricas."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from core.analytics.domain.enums import LoadMode, RunStatus
from core.analytics.domain.exceptions import AnalyticsDisabledError, PipelineStepError
from core.analytics.domain.interfaces import IAnalyticsStore, IPipeline
from core.analytics.domain.schemas import (
    ExtractBatch,
    LoadTarget,
    PipelineContext,
    PipelineResult,
    StepMetric,
    TransformBatch,
    Watermark,
)
from core.analytics.observability import metrics

logger = logging.getLogger('app.analytics')


class PipelineRunner:
    """Orquesta pasos ETL medidos. Sin Celery (eso es Fase 3)."""

    def __init__(self, store: IAnalyticsStore):
        self.store = store

    def run(self, pipeline: IPipeline, ctx: PipelineContext) -> PipelineResult:
        from core.analytics.config import is_analytics_enabled

        if not is_analytics_enabled():
            raise AnalyticsDisabledError('ANALYTICS_ENABLED=false')

        started_mono = time.monotonic()
        started_at = datetime.now(timezone.utc)
        steps: list[StepMetric] = []
        watermark_before = ctx.watermark or self.store.get_watermark(
            ctx.company_id, ctx.pipeline_key,
        )
        if ctx.watermark is None and watermark_before is not None:
            ctx = ctx.model_copy(update={'watermark': watermark_before})

        rows_extracted = 0
        rows_staged = 0
        rows_transformed = 0
        rows_loaded = 0
        watermark_after: Optional[Watermark] = None

        try:
            extracted, extract_metric = self._timed_step(
                'extract',
                lambda: pipeline.extract(ctx),
            )
            steps.append(extract_metric)
            assert isinstance(extracted, ExtractBatch)
            rows_extracted = len(extracted.rows)

            if ctx.dry_run:
                result = self._result(
                    ctx,
                    RunStatus.SUCCESS,
                    started_mono,
                    watermark_before=watermark_before,
                    rows_extracted=rows_extracted,
                    steps=steps,
                )
                metrics.increment('analytics.pipeline.dry_run')
                self._safe_record(result, ctx, started_at)
                return result

            staged_count, stage_metric = self._timed_step(
                'stage',
                lambda: self.store.load_staging(
                    pipeline.staging_name(),
                    extracted.rows,
                    company_id=ctx.company_id,
                    replace=True,
                ),
            )
            steps.append(stage_metric)
            rows_staged = int(staged_count)

            staged_rows, read_metric = self._timed_step(
                'read_staging',
                lambda: self.store.read_staging(
                    pipeline.staging_name(),
                    company_id=ctx.company_id,
                ),
            )
            steps.append(read_metric)
            assert isinstance(staged_rows, list)

            transformed, transform_metric = self._timed_step(
                'transform',
                lambda: pipeline.transform(ctx, staged_rows),
            )
            steps.append(transform_metric)
            assert isinstance(transformed, TransformBatch)
            rows_transformed = len(transformed.rows)

            loaded_count, load_metric = self._timed_step(
                'load',
                lambda: self._publish(ctx, transformed.rows, transformed.target),
            )
            steps.append(load_metric)
            rows_loaded = int(loaded_count)

            watermark_after = pipeline.next_watermark(ctx, extracted)
            if watermark_after is not None:
                self.store.set_watermark(ctx.company_id, ctx.pipeline_key, watermark_after)

            result = self._result(
                ctx,
                RunStatus.SUCCESS,
                started_mono,
                watermark_before=watermark_before,
                watermark_after=watermark_after,
                rows_extracted=rows_extracted,
                rows_staged=rows_staged,
                rows_transformed=rows_transformed,
                rows_loaded=rows_loaded,
                steps=steps,
            )
            metrics.increment('analytics.pipeline.success')
            metrics.increment('analytics.rows.loaded', rows_loaded)
            self._safe_record(result, ctx, started_at)
            return result
        except PipelineStepError as exc:
            metrics.increment('analytics.pipeline.failed')
            logger.exception(
                'analytics pipeline failed key=%s company=%s step=%s',
                ctx.pipeline_key,
                ctx.company_id,
                exc.step,
            )
            result = self._result(
                ctx,
                RunStatus.FAILED,
                started_mono,
                watermark_before=watermark_before,
                rows_extracted=rows_extracted,
                rows_staged=rows_staged,
                rows_transformed=rows_transformed,
                rows_loaded=rows_loaded,
                steps=steps,
                error=str(exc),
            )
            self._safe_record(result, ctx, started_at)
            return result
        except Exception as exc:
            metrics.increment('analytics.pipeline.failed')
            logger.exception(
                'analytics pipeline unexpected failure key=%s company=%s',
                ctx.pipeline_key,
                ctx.company_id,
            )
            result = self._result(
                ctx,
                RunStatus.FAILED,
                started_mono,
                watermark_before=watermark_before,
                rows_extracted=rows_extracted,
                rows_staged=rows_staged,
                rows_transformed=rows_transformed,
                rows_loaded=rows_loaded,
                steps=steps,
                error=str(exc),
            )
            self._safe_record(result, ctx, started_at)
            return result

    def _safe_record(
        self,
        result: PipelineResult,
        ctx: PipelineContext,
        started_at: datetime,
    ) -> None:
        try:
            self.store.record_pipeline_run(
                run_id=result.run_id,
                company_id=result.company_id,
                pipeline_key=result.pipeline_key,
                status=result.status.value,
                trigger=ctx.trigger.value,
                rows_extracted=result.rows_extracted,
                rows_loaded=result.rows_loaded,
                error=result.error or '',
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                steps=result.steps,
            )
        except Exception:
            logger.exception(
                'analytics failed to record pipeline run key=%s run_id=%s',
                result.pipeline_key,
                result.run_id,
            )

    @staticmethod
    def _result(
        ctx: PipelineContext,
        status: RunStatus,
        started_mono: float,
        *,
        watermark_before: Optional[Watermark] = None,
        watermark_after: Optional[Watermark] = None,
        rows_extracted: int = 0,
        rows_staged: int = 0,
        rows_transformed: int = 0,
        rows_loaded: int = 0,
        steps: list[StepMetric] | None = None,
        error: str | None = None,
    ) -> PipelineResult:
        return PipelineResult(
            status=status,
            pipeline_key=ctx.pipeline_key,
            company_id=ctx.company_id,
            run_id=ctx.run_id,
            rows_extracted=rows_extracted,
            rows_staged=rows_staged,
            rows_transformed=rows_transformed,
            rows_loaded=rows_loaded,
            watermark_before=watermark_before,
            watermark_after=watermark_after,
            duration_ms=int((time.monotonic() - started_mono) * 1000),
            error=error,
            steps=steps or [],
        )

    def _publish(
        self,
        ctx: PipelineContext,
        rows: list[dict[str, Any]],
        target: LoadTarget,
    ) -> int:
        if target.mode == LoadMode.NOOP or not target.name:
            return 0
        company_id: UUID = ctx.company_id
        if target.mode == LoadMode.UPSERT_DIMENSION:
            return self.store.upsert_dimension(target.name, rows, company_id=company_id)
        if target.mode == LoadMode.APPEND_FACTS:
            return self.store.append_facts(target.name, rows, company_id=company_id)
        if target.mode == LoadMode.MERGE_FACTS:
            return self.store.merge_facts(
                target.name, rows, target.merge_keys, company_id=company_id,
            )
        raise PipelineStepError('load', f'Unsupported load mode {target.mode!r}')

    def _timed_step(self, step: str, fn):
        t0 = time.monotonic()
        try:
            result = fn()
            duration_ms = int((time.monotonic() - t0) * 1000)
            rows = 0
            if isinstance(result, ExtractBatch):
                rows = len(result.rows)
            elif isinstance(result, TransformBatch):
                rows = len(result.rows)
            elif isinstance(result, list):
                rows = len(result)
            elif isinstance(result, int):
                rows = result
            return result, StepMetric(step=step, rows=rows, duration_ms=duration_ms, ok=True)
        except PipelineStepError:
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            raise PipelineStepError(step, str(exc), cause=exc) from exc
