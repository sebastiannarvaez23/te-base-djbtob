"""Puertos del dominio analytics / ETL."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from .schemas import (
    AnalyticsQuery,
    AnalyticsResult,
    ExtractBatch,
    LoadTarget,
    PipelineContext,
    StepMetric,
    TransformBatch,
    TransformPlan,
    TransformResult,
    Watermark,
)


class IAnalyticsStore(ABC):
    """Persistencia del DW (stg / dw / ctl). El resto del mono solo ve este puerto."""

    @abstractmethod
    def upsert_dimension(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
    ) -> int:
        ...

    @abstractmethod
    def append_facts(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
    ) -> int:
        ...

    @abstractmethod
    def merge_facts(
        self,
        name: str,
        rows: list[dict[str, Any]],
        keys: list[str],
        *,
        company_id: UUID,
    ) -> int:
        ...

    @abstractmethod
    def load_staging(
        self,
        name: str,
        rows: list[dict[str, Any]],
        *,
        company_id: UUID,
        replace: bool = True,
    ) -> int:
        ...

    @abstractmethod
    def read_staging(self, name: str, *, company_id: UUID) -> list[dict[str, Any]]:
        """Rows previously written by ``load_staging`` for this company."""
        ...

    @abstractmethod
    def query(self, request: AnalyticsQuery) -> AnalyticsResult:
        ...

    @abstractmethod
    def execute_transform(self, plan: TransformPlan) -> TransformResult:
        """Hook ELT; en MVP ETL puede no-op o NotImplemented."""
        ...

    @abstractmethod
    def get_watermark(self, company_id: UUID, pipeline_key: str) -> Optional[Watermark]:
        ...

    @abstractmethod
    def set_watermark(
        self,
        company_id: UUID,
        pipeline_key: str,
        watermark: Watermark,
    ) -> None:
        ...

    @abstractmethod
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
        """Persist ctl.pipeline_runs (+ steps when supported)."""
        ...


class IExtractor(ABC):

    @abstractmethod
    def extract(self, ctx: PipelineContext) -> ExtractBatch:
        ...


class ITransformer(ABC):

    @abstractmethod
    def transform(self, ctx: PipelineContext, rows: list[dict[str, Any]]) -> TransformBatch:
        ...


class ILoader(ABC):
    """Publica filas transformadas al mart vía store."""

    @abstractmethod
    def load(
        self,
        ctx: PipelineContext,
        store: IAnalyticsStore,
        rows: list[dict[str, Any]],
        target: LoadTarget,
    ) -> int:
        ...


class IPipeline(ABC):
    """Unidad ETL desacoplada (dimensions, inventory, …)."""

    key: str

    @abstractmethod
    def extract(self, ctx: PipelineContext) -> ExtractBatch:
        ...

    @abstractmethod
    def transform(self, ctx: PipelineContext, rows: list[dict[str, Any]]) -> TransformBatch:
        ...

    def staging_name(self) -> str:
        return f'stg_{self.key}'

    def next_watermark(
        self,
        ctx: PipelineContext,
        extracted: ExtractBatch,
    ) -> Optional[Watermark]:
        return extracted.next_watermark
