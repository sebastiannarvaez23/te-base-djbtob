"""
core/analytics
──────────────
Capa transversal del Data Warehouse (ETL / preparación ELT).

Gemelo de ``core/integrations/`` y ``core/ai/``: puertos en ``domain/``,
adaptadores en ``infrastructure/``, orquestación en ``application/``.
Ver ``docs/plan-datawarehouse/``.

Uso rápido::

    from uuid import uuid4
    from core.analytics import (
        get_analytics_store,
        run_pipeline,
        PipelineContext,
        Trigger,
    )

    store = get_analytics_store()  # fake por defecto (safe)
    result = run_pipeline(
        'null',
        PipelineContext(
            company_id=uuid4(),
            schema_name='demo',
            pipeline_key='null',
            trigger=Trigger.TEST,
        ),
        store=store,
    )
"""

from __future__ import annotations

from .application.pipeline_runner import PipelineRunner
from .application.query_service import QueryService
from .config import (
    get_analytics_store,
    get_pipeline,
    get_pipeline_registry,
    is_analytics_enabled,
)
from .domain import (
    AnalyticsDisabledError,
    AnalyticsError,
    AnalyticsQuery,
    AnalyticsQueryError,
    AnalyticsResult,
    ExtractBatch,
    IAnalyticsStore,
    IPipeline,
    LoadMode,
    LoadTarget,
    PipelineContext,
    PipelineKey,
    PipelineNotFoundError,
    PipelineResult,
    PipelineStepError,
    RunStatus,
    TransformBatch,
    TransformPlan,
    TransformResult,
    Trigger,
    Watermark,
    WatermarkStrategy,
)
from .infrastructure.fake_store import FakeAnalyticsStore
from .infrastructure.registry import PipelineRegistry
from .pipelines import NullPipeline


def run_pipeline(
    pipeline_key: str,
    ctx: PipelineContext,
    *,
    store: IAnalyticsStore | None = None,
    runner: PipelineRunner | None = None,
) -> PipelineResult:
    """Resuelve el pipeline, ejecuta extract→stage→transform→load."""
    resolved_store = store or get_analytics_store()
    pipeline = get_pipeline(pipeline_key)
    if ctx.pipeline_key != pipeline_key:
        ctx = ctx.model_copy(update={'pipeline_key': pipeline_key})
    return (runner or PipelineRunner(store=resolved_store)).run(pipeline, ctx)


__all__ = [
    'AnalyticsDisabledError',
    'AnalyticsError',
    'AnalyticsQuery',
    'AnalyticsQueryError',
    'AnalyticsResult',
    'ExtractBatch',
    'FakeAnalyticsStore',
    'IAnalyticsStore',
    'IPipeline',
    'LoadMode',
    'LoadTarget',
    'NullPipeline',
    'PipelineContext',
    'PipelineKey',
    'PipelineNotFoundError',
    'PipelineRegistry',
    'PipelineResult',
    'PipelineRunner',
    'PipelineStepError',
    'QueryService',
    'RunStatus',
    'TransformBatch',
    'TransformPlan',
    'TransformResult',
    'Trigger',
    'Watermark',
    'WatermarkStrategy',
    'get_analytics_store',
    'get_pipeline',
    'get_pipeline_registry',
    'is_analytics_enabled',
    'run_pipeline',
]
