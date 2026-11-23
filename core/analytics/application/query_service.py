"""Lecturas tipadas del mart (stubs listos para Fase 6)."""

from __future__ import annotations

from core.analytics.domain.exceptions import AnalyticsQueryError
from core.analytics.domain.interfaces import IAnalyticsStore
from core.analytics.domain.schemas import AnalyticsQuery, AnalyticsResult


class QueryService:
    """Facade de lectura. Exige ``company_id`` (validado por schema Pydantic)."""

    def __init__(self, store: IAnalyticsStore):
        self.store = store

    def execute(self, request: AnalyticsQuery) -> AnalyticsResult:
        if request.company_id is None:
            raise AnalyticsQueryError('company_id is required')
        if not request.dataset:
            raise AnalyticsQueryError('dataset is required')
        return self.store.query(request)
