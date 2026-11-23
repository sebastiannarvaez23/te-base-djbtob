"""Tests FakeAnalyticsStore aislados."""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.analytics import AnalyticsQuery, FakeAnalyticsStore, TransformPlan, Watermark, WatermarkStrategy


@pytest.mark.unit
class TestFakeAnalyticsStore:

    def test_upsert_dimension_by_source_id(self):
        store = FakeAnalyticsStore()
        cid = uuid4()
        store.upsert_dimension(
            'dim_x',
            [{'source_id': 'a', 'name': 'one'}],
            company_id=cid,
        )
        store.upsert_dimension(
            'dim_x',
            [{'source_id': 'a', 'name': 'two'}],
            company_id=cid,
        )
        assert len(store.dimensions['dim_x']) == 1
        assert store.dimensions['dim_x'][0]['name'] == 'two'

    def test_merge_facts_by_keys(self):
        store = FakeAnalyticsStore()
        cid = uuid4()
        store.merge_facts(
            'fact_x',
            [{'source_id': '1', 'v': 1}],
            ['source_id'],
            company_id=cid,
        )
        store.merge_facts(
            'fact_x',
            [{'source_id': '1', 'v': 9}],
            ['source_id'],
            company_id=cid,
        )
        assert len(store.facts['fact_x']) == 1
        assert store.facts['fact_x'][0]['v'] == 9

    def test_staging_replace_per_company(self):
        store = FakeAnalyticsStore()
        a, b = uuid4(), uuid4()
        store.load_staging('stg_t', [{'x': 1}], company_id=a, replace=True)
        store.load_staging('stg_t', [{'x': 2}], company_id=b, replace=True)
        store.load_staging('stg_t', [{'x': 3}], company_id=a, replace=True)
        rows_a = [r for r in store.staging['stg_t'] if r['company_id'] == str(a)]
        rows_b = [r for r in store.staging['stg_t'] if r['company_id'] == str(b)]
        assert len(rows_a) == 1 and rows_a[0]['x'] == 3
        assert len(rows_b) == 1 and rows_b[0]['x'] == 2

    def test_watermark_roundtrip(self):
        store = FakeAnalyticsStore()
        cid = uuid4()
        wm = Watermark(strategy=WatermarkStrategy.OPAQUE, cursor_opaque='c1')
        store.set_watermark(cid, 'inventory', wm)
        assert store.get_watermark(cid, 'inventory').cursor_opaque == 'c1'

    def test_execute_transform_records_plan(self):
        store = FakeAnalyticsStore()
        plan = TransformPlan(name='noop', sql='SELECT 1')
        result = store.execute_transform(plan)
        assert result.rows_affected == 0
        assert store.transform_calls == [plan]

    def test_query_empty_dataset(self):
        store = FakeAnalyticsStore()
        result = store.query(AnalyticsQuery(company_id=uuid4(), dataset='missing'))
        assert result.total == 0
        assert result.rows == []

    def test_dim_date_is_global_not_sealed_by_company(self):
        store = FakeAnalyticsStore()
        a, b = uuid4(), uuid4()
        store.upsert_dimension(
            'dim_date',
            [{'date_key': 20240101, 'full_date': '2024-01-01', 'year': 2024,
              'quarter': 1, 'month': 1, 'day': 1, 'week_iso': 1,
              'day_of_week': 1, 'is_weekend': False}],
            company_id=a,
        )
        result = store.query(AnalyticsQuery(company_id=b, dataset='dim_date'))
        assert result.total == 1
        assert 'company_id' not in result.rows[0]

    def test_query_total_ignores_limit(self):
        store = FakeAnalyticsStore()
        cid = uuid4()
        store.append_facts(
            'fact_x',
            [{'n': i} for i in range(5)],
            company_id=cid,
        )
        result = store.query(AnalyticsQuery(company_id=cid, dataset='fact_x', limit=2))
        assert result.total == 5
        assert len(result.rows) == 2

    def test_read_staging_roundtrip(self):
        store = FakeAnalyticsStore()
        cid = uuid4()
        store.load_staging('stg_t', [{'x': 1}], company_id=cid, replace=True)
        rows = store.read_staging('stg_t', company_id=cid)
        assert rows == [{'x': 1, 'company_id': str(cid)}]
