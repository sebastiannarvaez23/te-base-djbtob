"""Factory y configuración de analytics / ETL."""

from __future__ import annotations

from django.conf import settings

from core.analytics.domain.interfaces import IAnalyticsStore, IPipeline
from core.analytics.infrastructure.registry import PipelineRegistry


def is_analytics_enabled() -> bool:
    return bool(getattr(settings, 'ANALYTICS_ENABLED', True))


def get_analytics_store_kind() -> str:
    return str(getattr(settings, 'ANALYTICS_STORE', 'fake')).lower()


def get_analytics_store() -> IAnalyticsStore:
    kind = get_analytics_store_kind()
    if kind == 'postgres':
        from core.analytics.infrastructure.postgres_store import PostgresAnalyticsStore
        return PostgresAnalyticsStore()
    from core.analytics.infrastructure.fake_store import FakeAnalyticsStore
    return FakeAnalyticsStore()


_BUILTIN_REGISTERED = False


def _ensure_pipelines_registered() -> None:
    global _BUILTIN_REGISTERED
    if not _BUILTIN_REGISTERED:
        from core.analytics.pipelines import register_builtin_pipelines
        register_builtin_pipelines()
        _BUILTIN_REGISTERED = True


def get_pipeline_registry() -> PipelineRegistry:
    _ensure_pipelines_registered()
    return PipelineRegistry()


def get_pipeline(key: str) -> IPipeline:
    return get_pipeline_registry().create(key)
