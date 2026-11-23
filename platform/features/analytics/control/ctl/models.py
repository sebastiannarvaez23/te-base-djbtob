"""
ORM mirrors of ctl.* / dw.* on DATABASES['analytics'] (wadw).

Tables are created by RunSQL migrations (schemas ctl/stg/dw). Models are
``managed = False`` so Django never invents them on ``default``.
"""

from __future__ import annotations

from django.db import models

from core.ids import uuid7


class PipelineWatermark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    company_id = models.UUIDField()
    pipeline_key = models.CharField(max_length=64)
    strategy = models.CharField(max_length=32, default='TIMESTAMP')
    cursor_ts = models.DateTimeField(null=True, blank=True)
    cursor_id = models.CharField(max_length=64, null=True, blank=True)
    cursor_opaque = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        app_label = 'analytics_ctl'
        db_table = 'pipeline_watermarks'
        constraints = [
            models.UniqueConstraint(
                fields=['company_id', 'pipeline_key'],
                name='uq_ctl_watermark_company_pipeline',
            ),
        ]


class PipelineRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    company_id = models.UUIDField()
    pipeline_key = models.CharField(max_length=64)
    status = models.CharField(max_length=32)
    trigger = models.CharField(max_length=32)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    rows_extracted = models.IntegerField(default=0)
    rows_loaded = models.IntegerField(default=0)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        app_label = 'analytics_ctl'
        db_table = 'pipeline_runs'


class PipelineRunStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    run_id = models.UUIDField()
    step = models.CharField(max_length=64)
    status = models.CharField(max_length=32)
    rows_count = models.IntegerField(default=0)
    duration_ms = models.IntegerField(default=0)
    error = models.TextField(blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        app_label = 'analytics_ctl'
        db_table = 'pipeline_run_steps'


class DimDate(models.Model):
    date_key = models.IntegerField(primary_key=True)
    full_date = models.DateField(unique=True)
    year = models.SmallIntegerField()
    quarter = models.SmallIntegerField()
    month = models.SmallIntegerField()
    day = models.SmallIntegerField()
    week_iso = models.SmallIntegerField()
    day_of_week = models.SmallIntegerField()
    is_weekend = models.BooleanField()

    class Meta:
        managed = False
        app_label = 'analytics_ctl'
        db_table = 'dim_date'


class DimCompany(models.Model):
    company_sk = models.BigAutoField(primary_key=True)
    company_id = models.UUIDField(unique=True)
    schema_name = models.CharField(max_length=63)
    name = models.CharField(max_length=200)
    nit = models.CharField(max_length=40, blank=True, default='')
    lifecycle = models.CharField(max_length=16, default='ACTIVE')
    is_active = models.BooleanField(default=True)
    loaded_at = models.DateTimeField()

    class Meta:
        managed = False
        app_label = 'analytics_ctl'
        db_table = 'dim_company'
