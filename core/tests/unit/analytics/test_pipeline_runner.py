"""Tests del PipelineRunner y facade run_pipeline."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from core.analytics import (
    AnalyticsDisabledError,
    ExtractBatch,
    FakeAnalyticsStore,
    LoadMode,
    LoadTarget,
    NullPipeline,
    PipelineContext,
    PipelineKey,
    PipelineNotFoundError,
    PipelineResult,
    PipelineRunner,
    QueryService,
    RunStatus,
    TransformBatch,
    Trigger,
    Watermark,
    WatermarkStrategy,
    get_analytics_store,
    is_analytics_enabled,
    run_pipeline,
)
from core.analytics.domain.interfaces import IPipeline
from core.analytics.infrastructure.registry import clear_registry, register_pipeline
from core.analytics.observability.metrics import reset_metrics
from core.analytics.pipelines import register_builtin_pipelines


@pytest.fixture(autouse=True)
def _reset_analytics_state(settings):
    settings.ANALYTICS_ENABLED = True
    settings.ANALYTICS_STORE = 'fake'
    clear_registry()
    register_builtin_pipelines()
    reset_metrics()
    # Force config to re-register builtins after clear on next get_pipeline.
    import core.analytics.config as cfg
    cfg._BUILTIN_REGISTERED = True
    yield
    clear_registry()
    reset_metrics()


def _ctx(**kwargs) -> PipelineContext:
    base = dict(
        company_id=uuid4(),
        schema_name='demo',
        pipeline_key=PipelineKey.NULL.value,
        trigger=Trigger.TEST,
    )
    base.update(kwargs)
    return PipelineContext(**base)


class _RecordingPipeline(IPipeline):
    key = 'recording'

    def __init__(self):
        self.load_calls = 0
        self.transform_calls = 0

    def extract(self, ctx: PipelineContext) -> ExtractBatch:
        return ExtractBatch(
            rows=[{'source_id': '1', 'qty': 2}],
            next_watermark=Watermark(
                strategy=WatermarkStrategy.TIMESTAMP,
                cursor_opaque='wm-1',
            ),
        )

    def transform(self, ctx: PipelineContext, rows: list[dict[str, Any]]) -> TransformBatch:
        self.transform_calls += 1
        return TransformBatch(
            rows=[{**r, 'qty': r['qty'] * 10} for r in rows],
            target=LoadTarget(mode=LoadMode.APPEND_FACTS, name='fact_demo'),
        )


class _FailingTransformPipeline(_RecordingPipeline):
    key = 'fail_transform'

    def transform(self, ctx: PipelineContext, rows: list[dict[str, Any]]) -> TransformBatch:
        self.transform_calls += 1
        raise RuntimeError('boom-transform')


@pytest.mark.unit
class TestConfig:

    def test_analytics_enabled_default(self):
        assert is_analytics_enabled() is True

    def test_get_analytics_store_defaults_to_fake(self):
        assert isinstance(get_analytics_store(), FakeAnalyticsStore)


@pytest.mark.unit
class TestNullPipeline:

    def test_run_pipeline_null_success_zero_rows(self):
        store = FakeAnalyticsStore()
        result = run_pipeline(PipelineKey.NULL.value, _ctx(), store=store)
        assert isinstance(result, PipelineResult)
        assert result.status == RunStatus.SUCCESS
        assert result.rows_extracted == 0
        assert result.rows_loaded == 0
        assert [s.step for s in result.steps] == [
            'extract', 'stage', 'read_staging', 'transform', 'load',
        ]
        assert len(store.runs) == 1
        assert store.runs[0]['status'] == RunStatus.SUCCESS.value

    def test_unknown_pipeline_raises(self):
        with pytest.raises(PipelineNotFoundError):
            run_pipeline('nope', _ctx(pipeline_key='nope'), store=FakeAnalyticsStore())


@pytest.mark.unit
class TestPipelineRunner:

    def test_happy_path_loads_and_sets_watermark(self):
        store = FakeAnalyticsStore()
        pipeline = _RecordingPipeline()
        register_pipeline(pipeline.key, _RecordingPipeline)
        ctx = _ctx(pipeline_key=pipeline.key)
        result = PipelineRunner(store=store).run(pipeline, ctx)
        assert result.status == RunStatus.SUCCESS
        assert result.rows_extracted == 1
        assert result.rows_staged == 1
        assert result.rows_transformed == 1
        assert result.rows_loaded == 1
        assert store.facts['fact_demo'][0]['qty'] == 20
        assert store.get_watermark(ctx.company_id, pipeline.key).cursor_opaque == 'wm-1'
        assert store.read_staging(pipeline.staging_name(), company_id=ctx.company_id)
        assert store.runs and store.runs[0]['rows_loaded'] == 1

    def test_transform_reads_from_staging_not_extract_only(self):
        store = FakeAnalyticsStore()

        class _StagingAware(IPipeline):
            key = 'staging_aware'

            def extract(self, ctx: PipelineContext) -> ExtractBatch:
                return ExtractBatch(rows=[{'source_id': '1', 'qty': 1}])

            def transform(self, ctx: PipelineContext, rows: list[dict[str, Any]]) -> TransformBatch:
                # Must see company_id sealed by load_staging.
                assert rows and 'company_id' in rows[0]
                return TransformBatch(
                    rows=rows,
                    target=LoadTarget(mode=LoadMode.APPEND_FACTS, name='fact_s'),
                )

        pipeline = _StagingAware()
        result = PipelineRunner(store=store).run(pipeline, _ctx(pipeline_key=pipeline.key))
        assert result.status == RunStatus.SUCCESS
        assert result.rows_loaded == 1

    def test_run_id_is_uuid7(self):
        ctx = _ctx()
        assert ctx.run_id.version == 7

    def test_transform_failure_does_not_call_load(self):
        store = FakeAnalyticsStore()
        pipeline = _FailingTransformPipeline()
        ctx = _ctx(pipeline_key=pipeline.key)
        result = PipelineRunner(store=store).run(pipeline, ctx)
        assert result.status == RunStatus.FAILED
        assert 'boom-transform' in (result.error or '')
        assert 'fact_demo' not in store.facts
        assert store.get_watermark(ctx.company_id, pipeline.key) is None
        step_names = [s.step for s in result.steps]
        assert 'extract' in step_names
        assert 'stage' in step_names
        assert 'load' not in step_names
        assert store.runs and store.runs[0]['status'] == RunStatus.FAILED.value

    def test_disabled_raises(self, settings):
        settings.ANALYTICS_ENABLED = False
        with pytest.raises(AnalyticsDisabledError):
            PipelineRunner(store=FakeAnalyticsStore()).run(NullPipeline(), _ctx())


@pytest.mark.unit
class TestQueryService:

    def test_query_filters_by_company(self):
        store = FakeAnalyticsStore()
        company_a = uuid4()
        company_b = uuid4()
        store.append_facts('fact_demo', [{'n': 1}], company_id=company_a)
        store.append_facts('fact_demo', [{'n': 2}], company_id=company_b)
        from core.analytics import AnalyticsQuery

        result = QueryService(store).execute(
            AnalyticsQuery(company_id=company_a, dataset='fact_demo'),
        )
        assert result.total == 1
        assert result.rows[0]['n'] == 1
