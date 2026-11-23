"""Unit tests — agent run list admin (paginated)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from core.query import PaginatedQuery

from platform.features.configuration.ai.run_observability.application.use_cases import (
    ListAgentRunsAdminUseCase,
)
from platform.features.configuration.ai.run_observability.domain.schemas import (
    AgentRunListItemSchema,
)


class FakeProbe:
    def __init__(self, rows):
        self.rows = rows

    def collect_recent(self, *, status=None, per_tenant_limit=20, max_tenants=50):
        if status:
            return [r for r in self.rows if r.status == status]
        return list(self.rows)


@pytest.mark.unit
def test_list_runs_paginates():
    now = datetime.now(timezone.utc)
    rows = [
        AgentRunListItemSchema(
            id=uuid4(),
            tenant_schema=f't{i}',
            user_id=uuid4(),
            status='completed',
            created_at=now,
        )
        for i in range(5)
    ]
    result = ListAgentRunsAdminUseCase(FakeProbe(rows)).execute(
        PaginatedQuery(page=0, page_size=2, filters={}),
    )
    assert result.total == 5
    assert len(result.items) == 2
    assert result.page == 0
    assert result.page_size == 2
    assert result.sampled is True
    assert result.max_tenants == 50
    assert result.per_tenant_limit == 20


@pytest.mark.unit
def test_list_runs_sorts_null_timestamps():
    rows = [
        AgentRunListItemSchema(
            id=uuid4(),
            tenant_schema='t0',
            user_id=uuid4(),
            status='running',
            created_at=None,
            started_at=None,
            finished_at=None,
        ),
        AgentRunListItemSchema(
            id=uuid4(),
            tenant_schema='t1',
            user_id=uuid4(),
            status='completed',
            created_at=datetime.now(timezone.utc),
        ),
    ]
    result = ListAgentRunsAdminUseCase(FakeProbe(rows)).execute(
        PaginatedQuery(page=0, page_size=10, filters={}),
    )
    assert len(result.items) == 2
    assert result.items[0].status == 'completed'
