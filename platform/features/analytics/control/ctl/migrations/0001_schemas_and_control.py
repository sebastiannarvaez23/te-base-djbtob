"""DDL only: schemas ctl/stg/dw + control tables + dim_date/dim_company.

No business seed data (dim_date is loaded via ``load_dim_date`` command).
"""

from django.db import migrations

FORWARD = r"""
CREATE SCHEMA IF NOT EXISTS ctl;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS dw;

CREATE TABLE IF NOT EXISTS ctl.pipeline_watermarks (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL,
    pipeline_key VARCHAR(64) NOT NULL,
    strategy VARCHAR(32) NOT NULL DEFAULT 'TIMESTAMP',
    cursor_ts TIMESTAMPTZ NULL,
    cursor_id VARCHAR(64) NULL,
    cursor_opaque TEXT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ctl_watermark_company_pipeline UNIQUE (company_id, pipeline_key)
);

CREATE TABLE IF NOT EXISTS ctl.pipeline_runs (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL,
    pipeline_key VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    trigger VARCHAR(32) NOT NULL,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    rows_extracted INTEGER NOT NULL DEFAULT 0,
    rows_loaded INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ctl_pipeline_runs_company_key
    ON ctl.pipeline_runs (company_id, pipeline_key, created_at DESC);

CREATE TABLE IF NOT EXISTS ctl.pipeline_run_steps (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES ctl.pipeline_runs(id),
    step VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    rows_count INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_ctl_pipeline_run_steps_run
    ON ctl.pipeline_run_steps (run_id);

CREATE TABLE IF NOT EXISTS stg.raw_batches (
    id BIGSERIAL PRIMARY KEY,
    company_id UUID NOT NULL,
    staging_name VARCHAR(128) NOT NULL,
    row_payload JSONB NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stg_raw_batches_company_name
    ON stg.raw_batches (company_id, staging_name);

CREATE TABLE IF NOT EXISTS dw.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year SMALLINT NOT NULL,
    quarter SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    day SMALLINT NOT NULL,
    week_iso SMALLINT NOT NULL,
    day_of_week SMALLINT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS dw.dim_company (
    company_sk BIGSERIAL PRIMARY KEY,
    company_id UUID NOT NULL UNIQUE,
    schema_name VARCHAR(63) NOT NULL,
    name VARCHAR(200) NOT NULL,
    nit VARCHAR(40) NOT NULL DEFAULT '',
    lifecycle VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

REVERSE = r"""
DROP TABLE IF EXISTS dw.dim_company;
DROP TABLE IF EXISTS dw.dim_date;
DROP TABLE IF EXISTS stg.raw_batches;
DROP TABLE IF EXISTS ctl.pipeline_run_steps;
DROP TABLE IF EXISTS ctl.pipeline_runs;
DROP TABLE IF EXISTS ctl.pipeline_watermarks;
DROP SCHEMA IF EXISTS dw;
DROP SCHEMA IF EXISTS stg;
DROP SCHEMA IF EXISTS ctl;
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.RunSQL(sql=FORWARD, reverse_sql=REVERSE),
    ]
