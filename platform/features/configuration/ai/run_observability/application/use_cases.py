from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from core.query import PaginatedQuery
from core.trace import trace_layer

from platform.features.configuration.ai.run_observability.domain.interfaces import IAgentRunProbe
from platform.features.configuration.ai.run_observability.domain.schemas import (
    AgentRunListResultSchema,
)
from platform.features.configuration.ai.run_observability.infrastructure.probes import (
    DEFAULT_MAX_TENANTS,
    DEFAULT_PER_TENANT,
)

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _sort_ts(row) -> datetime:
    return row.created_at or row.started_at or row.finished_at or _EPOCH


class ListAgentRunsAdminUseCase:
    def __init__(
        self,
        probe: IAgentRunProbe,
        *,
        max_tenants: int = DEFAULT_MAX_TENANTS,
        per_tenant_limit: int = DEFAULT_PER_TENANT,
    ):
        self.probe = probe
        self.max_tenants = max_tenants
        self.per_tenant_limit = per_tenant_limit

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> AgentRunListResultSchema:
        status: Optional[str] = query.filters.get('status')
        rows = self.probe.collect_recent(
            status=status,
            per_tenant_limit=self.per_tenant_limit,
            max_tenants=self.max_tenants,
        )
        rows.sort(key=_sort_ts, reverse=True)
        total = len(rows)
        if query.unpaginated:
            page_items = rows
            page = 0
            page_size = total or 1
        else:
            start = query.offset
            end = start + query.limit
            page_items = rows[start:end]
            page = query.page
            page_size = query.page_size
        return AgentRunListResultSchema(
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            sampled=True,
            max_tenants=self.max_tenants,
            per_tenant_limit=self.per_tenant_limit,
        )
