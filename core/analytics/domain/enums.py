"""Enumeraciones del dominio analytics / ETL."""

from enum import Enum


class PipelineKey(str, Enum):
    """Keys canónicos; Fase 3–5 registran implementaciones."""

    DIMENSIONS = 'dimensions'
    INVENTORY = 'inventory'
    ORDERS = 'orders'
    RECEIVING = 'receiving'
    PICKING = 'picking'
    OPERATIONS = 'operations'
    PACKING = 'packing'
    DISPATCH = 'dispatch'
    RETURNS = 'returns'
    ROLLUP_DAILY = 'rollup_daily'
    # Smoke / tests (Fase 1)
    NULL = 'null'


class RunStatus(str, Enum):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'


class Trigger(str, Enum):
    BEAT = 'BEAT'
    MANUAL = 'MANUAL'
    REPROCESS = 'REPROCESS'
    TEST = 'TEST'


class WatermarkStrategy(str, Enum):
    TIMESTAMP = 'TIMESTAMP'
    ID_CURSOR = 'ID_CURSOR'
    OPAQUE = 'OPAQUE'
    FULL_REFRESH = 'FULL_REFRESH'


class LoadMode(str, Enum):
    UPSERT_DIMENSION = 'UPSERT_DIMENSION'
    APPEND_FACTS = 'APPEND_FACTS'
    MERGE_FACTS = 'MERGE_FACTS'
    NOOP = 'NOOP'
