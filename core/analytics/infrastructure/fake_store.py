"""FakeAnalyticsStore — in-memory para tests unitarios offline."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from core.analytics.domain.interfaces import IAnalyticsStore
from core.analytics.domain.schemas import (
    AnalyticsQuery,
    AnalyticsResult,
    StepMetric,
    TransformPlan,
    TransformResult,
    Watermark,
)

# Calendar / conformed dims without tenant seal (match Postgres behaviour).
_GLOBAL_DATASETS = frozenset({'dim_date'})


class FakeAnalyticsStore(IAnalyticsStore):
    """Dims / facts / staging / watermarks en dicts. Sin Postgres."""

    def __init__(self) -> None:
        self.dimensions: dict[str, list[dict[str, Any]]] = {}
        self.facts: dict[str, list[dict[str, Any]]] = {}
        self.staging: dict[str, list[dict[str, Any]]] = {}
        self.watermarks: dict[tuple[str, str], Watermark] = {}
        self.transform_calls: list[TransformPlan] = []
        self.runs: list[dict[str, Any]] = []

    def upsert_dimension(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
    ) -> int:
        bucket = self.dimensions.setdefault(name, [])
        if name in _GLOBAL_DATASETS:
            key_field = 'date_key' if name == 'dim_date' else 'source_id'
            index = {
                str(r.get(key_field)): i
                for i, r in enumerate(bucket)
                if r.get(key_field) is not None
            }
            written = 0
            for row in rows:
                payload = dict(row)
                key = payload.get(key_field)
                if key is not None and str(key) in index:
                    bucket[index[str(key)]] = payload
                else:
                    bucket.append(payload)
                    if key is not None:
                        index[str(key)] = len(bucket) - 1
                written += 1
            return written

        sealed = [{**row, 'company_id': str(company_id)} for row in rows]
        by_source = {
            str(r.get('source_id')): i
            for i, r in enumerate(bucket)
            if r.get('source_id') is not None and str(r.get('company_id')) == str(company_id)
        }
        written = 0
        for row in sealed:
            sid = row.get('source_id')
            if sid is not None and str(sid) in by_source:
                bucket[by_source[str(sid)]] = row
            else:
                bucket.append(row)
                if sid is not None:
                    by_source[str(sid)] = len(bucket) - 1
            written += 1
        return written

    def append_facts(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
    ) -> int:
        bucket = self.facts.setdefault(name, [])
        sealed = [{**row, 'company_id': str(company_id)} for row in rows]
        bucket.extend(sealed)
        return len(sealed)

    def merge_facts(
        self,
        name: str,
        rows: list[dict[str, Any]],
        keys: list[str],
        *,
        company_id: UUID,
    ) -> int:
        bucket = self.facts.setdefault(name, [])
        index: dict[tuple, int] = {}
        for i, existing in enumerate(bucket):
            if str(existing.get('company_id')) != str(company_id):
                continue
            index[tuple(existing.get(k) for k in keys)] = i
        written = 0
        for row in rows:
            sealed = {**row, 'company_id': str(company_id)}
            key = tuple(sealed.get(k) for k in keys)
            if key in index:
                bucket[index[key]] = sealed
            else:
                bucket.append(sealed)
                index[key] = len(bucket) - 1
            written += 1
        return written

    def load_staging(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
        replace: bool = True,
    ) -> int:
        sealed = [{**row, 'company_id': str(company_id)} for row in rows]
        if replace:
            previous = [
                r for r in self.staging.get(name, [])
                if str(r.get('company_id')) != str(company_id)
            ]
            self.staging[name] = previous + sealed
        else:
            self.staging.setdefault(name, []).extend(sealed)
        return len(sealed)

    def read_staging(self, name: str, *, company_id: UUID) -> list[dict[str, Any]]:
        return [
            deepcopy(r)
            for r in self.staging.get(name, [])
            if str(r.get('company_id')) == str(company_id)
        ]

    def query(self, request: AnalyticsQuery) -> AnalyticsResult:
        dataset = request.dataset
        pool = self.facts.get(dataset) or self.dimensions.get(dataset) or []
        if dataset in _GLOBAL_DATASETS:
            filtered = [deepcopy(r) for r in pool]
        else:
            filtered = [
                deepcopy(r)
                for r in pool
                if str(r.get('company_id')) == str(request.company_id)
            ]
        for key, value in request.filters.items():
            filtered = [r for r in filtered if r.get(key) == value]
        total = len(filtered)
        slice_ = filtered[request.offset: request.offset + request.limit]
        return AnalyticsResult(rows=slice_, total=total)

    def execute_transform(self, plan: TransformPlan) -> TransformResult:
        self.transform_calls.append(plan)
        return TransformResult(rows_affected=0, detail='fake-noop')

    def get_watermark(self, company_id: UUID, pipeline_key: str) -> Optional[Watermark]:
        return self.watermarks.get((str(company_id), pipeline_key))

    def set_watermark(
        self,
        company_id: UUID,
        pipeline_key: str,
        watermark: Watermark,
    ) -> None:
        self.watermarks[(str(company_id), pipeline_key)] = watermark

    def record_pipeline_run(
        self,
        *,
        run_id: UUID,
        company_id: UUID,
        pipeline_key: str,
        status: str,
        trigger: str,
        rows_extracted: int = 0,
        rows_loaded: int = 0,
        error: str = '',
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        steps: list[StepMetric] | None = None,
    ) -> None:
        self.runs.append({
            'run_id': str(run_id),
            'company_id': str(company_id),
            'pipeline_key': pipeline_key,
            'status': status,
            'trigger': trigger,
            'rows_extracted': rows_extracted,
            'rows_loaded': rows_loaded,
            'error': error,
            'started_at': started_at,
            'finished_at': finished_at,
            'steps': [s.model_dump() for s in (steps or [])],
        })
