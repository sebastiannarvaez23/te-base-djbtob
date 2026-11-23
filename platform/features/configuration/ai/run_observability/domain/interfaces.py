from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .schemas import AgentRunListItemSchema


class IAgentRunProbe(ABC):
    """Lee AgentRuns tenant (best-effort, acotado)."""

    @abstractmethod
    def collect_recent(
        self,
        *,
        status: Optional[str] = None,
        per_tenant_limit: int = 20,
        max_tenants: int = 50,
    ) -> list[AgentRunListItemSchema]:
        ...
