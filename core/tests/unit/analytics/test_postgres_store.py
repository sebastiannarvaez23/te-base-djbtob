"""Unit tests for PostgresAnalyticsStore helpers (no live DB required)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from core.analytics.domain.schemas import StepMetric, Watermark
from core.analytics.domain.enums import WatermarkStrategy
from core.analytics.infrastructure.postgres_store import PostgresAnalyticsStore


@pytest.mark.unit
class TestPostgresAnalyticsStoreGuards:

    def test_rejects_invalid_identifiers(self):
        store = PostgresAnalyticsStore()
        with pytest.raises(ValueError):
            store._assert_ident('dim;drop')
        with pytest.raises(ValueError):
            store.load_staging('bad-name!', [], company_id=uuid4())

    def test_append_facts_not_implemented_until_fase_4(self):
        store = PostgresAnalyticsStore()
        with pytest.raises(NotImplementedError):
            store.append_facts('fact_x', [], company_id=uuid4())


@pytest.mark.unit
class TestPostgresAnalyticsStoreSqlShape:
    """Smoke that record/watermark SQL paths accept typed args (mocked cursor)."""

    def test_set_watermark_uses_atomic_and_uuid7(self, monkeypatch):
        store = PostgresAnalyticsStore()
        executed = []

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                executed.append((sql, params))

            def executemany(self, sql, params=None):
                executed.append((sql, params))

        class _Atomic:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr(store, '_cursor', lambda: _Cursor())
        monkeypatch.setattr(store, '_atomic', lambda: _Atomic())

        store.set_watermark(
            uuid4(),
            'null',
            Watermark(strategy=WatermarkStrategy.OPAQUE, cursor_opaque='x'),
        )
        assert executed
        params = executed[0][1]
        # id, company_id, pipeline_key, strategy, ...
        from uuid import UUID
        assert UUID(params[0]).version == 7

    def test_record_pipeline_run_inserts_steps(self, monkeypatch):
        store = PostgresAnalyticsStore()
        calls = []

        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, sql, params=None):
                calls.append(('execute', sql, params))

            def executemany(self, sql, params=None):
                calls.append(('executemany', sql, params))

        class _Atomic:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        monkeypatch.setattr(store, '_cursor', lambda: _Cursor())
        monkeypatch.setattr(store, '_atomic', lambda: _Atomic())

        store.record_pipeline_run(
            run_id=uuid4(),
            company_id=uuid4(),
            pipeline_key='null',
            status='SUCCESS',
            trigger='TEST',
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            steps=[StepMetric(step='extract', rows=0, duration_ms=1, ok=True)],
        )
        kinds = [c[0] for c in calls]
        assert 'execute' in kinds
        assert 'executemany' in kinds
