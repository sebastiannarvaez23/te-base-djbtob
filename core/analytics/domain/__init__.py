"""Re-exports del dominio analytics."""

from .enums import LoadMode, PipelineKey, RunStatus, Trigger, WatermarkStrategy
from .exceptions import (
    AnalyticsDisabledError,
    AnalyticsError,
    AnalyticsQueryError,
    PipelineNotFoundError,
    PipelineStepError,
)
from .interfaces import IAnalyticsStore, IExtractor, ILoader, IPipeline, ITransformer
from .schemas import (
    AnalyticsQuery,
    AnalyticsResult,
    ExtractBatch,
    LoadTarget,
    PipelineContext,
    PipelineResult,
    StepMetric,
    TransformBatch,
    TransformPlan,
    TransformResult,
    Watermark,
)

__all__ = [
    'AnalyticsDisabledError',
    'AnalyticsError',
    'AnalyticsQuery',
    'AnalyticsQueryError',
    'AnalyticsResult',
    'ExtractBatch',
    'IAnalyticsStore',
    'IExtractor',
    'ILoader',
    'IPipeline',
    'ITransformer',
    'LoadMode',
    'LoadTarget',
    'PipelineContext',
    'PipelineKey',
    'PipelineNotFoundError',
    'PipelineResult',
    'PipelineStepError',
    'RunStatus',
    'StepMetric',
    'TransformBatch',
    'TransformPlan',
    'TransformResult',
    'Trigger',
    'Watermark',
    'WatermarkStrategy',
]
