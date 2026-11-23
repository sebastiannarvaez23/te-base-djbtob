"""PostgresAnalyticsStore — DML real contra ``DATABASES['analytics']`` (wadw)."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from django.db import connections, transaction

from core.analytics.domain.enums import WatermarkStrategy
from core.analytics.domain.interfaces import IAnalyticsStore
from core.analytics.domain.schemas import (
    AnalyticsQuery,
    AnalyticsResult,
    StepMetric,
    TransformPlan,
    TransformResult,
    Watermark,
)
from core.analytics.infrastructure.db_router import ANALYTICS_DB_ALIAS
from core.ids import uuid7

_IDENT = re.compile(r'^[a-z][a-z0-9_]*$')
_STAGING_IDENT = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]*$')


class PostgresAnalyticsStore(IAnalyticsStore):
    db_alias = ANALYTICS_DB_ALIAS

    def _cursor(self):
        return connections[self.db_alias].cursor()

    def _atomic(self):
        return transaction.atomic(using=self.db_alias)

    @staticmethod
    def _assert_ident(name: str) -> str:
        if not _IDENT.match(name):
            raise ValueError(f'Invalid analytics identifier: {name!r}')
        return name

    def upsert_dimension(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
    ) -> int:
        name = self._assert_ident(name)
        if name == 'dim_company':
            return self._upsert_dim_company(rows)
        if name == 'dim_date':
            return self._upsert_dim_date(rows)
        raise NotImplementedError(
            f'PostgresAnalyticsStore.upsert_dimension({name!r}) — add DDL in a later phase',
        )

    def _upsert_dim_company(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO dw.dim_company (
                company_id, schema_name, name, nit, lifecycle, is_active, loaded_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (company_id) DO UPDATE SET
                schema_name = EXCLUDED.schema_name,
                name = EXCLUDED.name,
                nit = EXCLUDED.nit,
                lifecycle = EXCLUDED.lifecycle,
                is_active = EXCLUDED.is_active,
                loaded_at = EXCLUDED.loaded_at
        """
        now = datetime.now(timezone.utc)
        params = [
            (
                str(row['company_id']),
                row.get('schema_name', ''),
                row.get('name', ''),
                row.get('nit', ''),
                row.get('lifecycle', 'ACTIVE'),
                bool(row.get('is_active', True)),
                row.get('loaded_at') or now,
            )
            for row in rows
        ]
        with self._atomic():
            with self._cursor() as cursor:
                cursor.executemany(sql, params)
        return len(params)

    def _upsert_dim_date(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        sql = """
            INSERT INTO dw.dim_date (
                date_key, full_date, year, quarter, month, day,
                week_iso, day_of_week, is_weekend
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date_key) DO UPDATE SET
                full_date = EXCLUDED.full_date,
                year = EXCLUDED.year,
                quarter = EXCLUDED.quarter,
                month = EXCLUDED.month,
                day = EXCLUDED.day,
                week_iso = EXCLUDED.week_iso,
                day_of_week = EXCLUDED.day_of_week,
                is_weekend = EXCLUDED.is_weekend
        """
        params = [
            (
                row['date_key'],
                row['full_date'],
                row['year'],
                row['quarter'],
                row['month'],
                row['day'],
                row['week_iso'],
                row['day_of_week'],
                row['is_weekend'],
            )
            for row in rows
        ]
        with self._atomic():
            with self._cursor() as cursor:
                cursor.executemany(sql, params)
        return len(params)

    def append_facts(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
    ) -> int:
        raise NotImplementedError('PostgresAnalyticsStore.append_facts — Fase 4')

    def merge_facts(
        self,
        name: str,
        rows: list[dict[str, Any]],
        keys: list[str],
        *,
        company_id: UUID,
    ) -> int:
        raise NotImplementedError('PostgresAnalyticsStore.merge_facts — Fase 4')

    def load_staging(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
        replace: bool = True,
    ) -> int:
        staging_name = name
        if not _STAGING_IDENT.match(staging_name):
            raise ValueError(f'Invalid staging name: {staging_name!r}')
        with self._atomic():
            with self._cursor() as cursor:
                if replace:
                    cursor.execute(
                        'DELETE FROM stg.raw_batches WHERE company_id = %s AND staging_name = %s',
                        [str(company_id), staging_name],
                    )
                if rows:
                    cursor.executemany(
                        """
                        INSERT INTO stg.raw_batches (company_id, staging_name, row_payload)
                        VALUES (%s, %s, %s::jsonb)
                        """,
                        [
                            (str(company_id), staging_name, json.dumps(row, default=str))
                            for row in rows
                        ],
                    )
        return len(rows)

    def read_staging(self, name: str, *, company_id: UUID) -> list[dict[str, Any]]:
        staging_name = name
        if not _STAGING_IDENT.match(staging_name):
            raise ValueError(f'Invalid staging name: {staging_name!r}')
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT row_payload
                FROM stg.raw_batches
                WHERE company_id = %s AND staging_name = %s
                ORDER BY id
                """,
                [str(company_id), staging_name],
            )
            rows = []
            for (payload,) in cursor.fetchall():
                if isinstance(payload, str):
                    rows.append(json.loads(payload))
                else:
                    rows.append(dict(payload))
            return rows

    def query(self, request: AnalyticsQuery) -> AnalyticsResult:
        dataset = self._assert_ident(request.dataset)
        if dataset == 'dim_company':
            where = 'WHERE company_id = %s'
            params: list[Any] = [str(request.company_id)]
            from_sql = 'FROM dw.dim_company'
            select = """
                SELECT company_id::text, schema_name, name, nit, lifecycle, is_active
            """
        elif dataset == 'dim_date':
            where = 'WHERE 1=1'
            params = []
            from_sql = 'FROM dw.dim_date'
            select = """
                SELECT date_key, full_date, year, quarter, month, day,
                       week_iso, day_of_week, is_weekend
            """
            if 'date_key' in request.filters:
                where += ' AND date_key = %s'
                params.append(request.filters['date_key'])
            if 'full_date' in request.filters:
                where += ' AND full_date = %s'
                params.append(request.filters['full_date'])
        else:
            raise NotImplementedError(
                f'PostgresAnalyticsStore.query({dataset!r}) — Fase 4+',
            )

        count_sql = f'SELECT COUNT(*) {from_sql} {where}'
        data_sql = (
            f'{select} {from_sql} {where} '
            f'LIMIT {int(request.limit)} OFFSET {int(request.offset)}'
        )
        with self._cursor() as cursor:
            cursor.execute(count_sql, params)
            total = int(cursor.fetchone()[0])
            cursor.execute(data_sql, params)
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        for row in rows:
            for key, value in list(row.items()):
                if isinstance(value, (date, datetime)):
                    row[key] = value.isoformat()
                elif isinstance(value, UUID):
                    row[key] = str(value)
        return AnalyticsResult(rows=rows, total=total)

    def execute_transform(self, plan: TransformPlan) -> TransformResult:
        raise NotImplementedError(
            'PostgresAnalyticsStore.execute_transform — ELT futuro; no usado en ETL MVP',
        )

    def get_watermark(self, company_id: UUID, pipeline_key: str) -> Optional[Watermark]:
        with self._cursor() as cursor:
            cursor.execute(
                """
                SELECT strategy, cursor_ts, cursor_id, cursor_opaque
                FROM ctl.pipeline_watermarks
                WHERE company_id = %s AND pipeline_key = %s
                """,
                [str(company_id), pipeline_key],
            )
            row = cursor.fetchone()
        if row is None:
            return None
        strategy, cursor_ts, cursor_id, cursor_opaque = row
        try:
            strategy_enum = WatermarkStrategy(strategy)
        except ValueError:
            strategy_enum = WatermarkStrategy.OPAQUE
        return Watermark(
            strategy=strategy_enum,
            cursor_ts=cursor_ts,
            cursor_id=cursor_id,
            cursor_opaque=cursor_opaque,
        )

    def set_watermark(
        self,
        company_id: UUID,
        pipeline_key: str,
        watermark: Watermark,
    ) -> None:
        with self._atomic():
            with self._cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ctl.pipeline_watermarks (
                        id, company_id, pipeline_key, strategy,
                        cursor_ts, cursor_id, cursor_opaque, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (company_id, pipeline_key) DO UPDATE SET
                        strategy = EXCLUDED.strategy,
                        cursor_ts = EXCLUDED.cursor_ts,
                        cursor_id = EXCLUDED.cursor_id,
                        cursor_opaque = EXCLUDED.cursor_opaque,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        str(uuid7()),
                        str(company_id),
                        pipeline_key,
                        watermark.strategy.value,
                        watermark.cursor_ts,
                        watermark.cursor_id,
                        watermark.cursor_opaque,
                        datetime.now(timezone.utc),
                    ],
                )

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
        with self._atomic():
            with self._cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ctl.pipeline_runs (
                        id, company_id, pipeline_key, status, trigger,
                        started_at, finished_at, rows_extracted, rows_loaded,
                        error, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        finished_at = EXCLUDED.finished_at,
                        rows_extracted = EXCLUDED.rows_extracted,
                        rows_loaded = EXCLUDED.rows_loaded,
                        error = EXCLUDED.error
                    """,
                    [
                        str(run_id),
                        str(company_id),
                        pipeline_key,
                        status,
                        trigger,
                        started_at,
                        finished_at,
                        rows_extracted,
                        rows_loaded,
                        error or '',
                        datetime.now(timezone.utc),
                    ],
                )
                if steps:
                    cursor.executemany(
                        """
                        INSERT INTO ctl.pipeline_run_steps (
                            id, run_id, step, status, rows_count, duration_ms, error
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            (
                                str(uuid7()),
                                str(run_id),
                                step.step,
                                'SUCCESS' if step.ok else 'FAILED',
                                step.rows,
                                step.duration_ms,
                                step.error or '',
                            )
                            for step in steps
                        ],
                    )
