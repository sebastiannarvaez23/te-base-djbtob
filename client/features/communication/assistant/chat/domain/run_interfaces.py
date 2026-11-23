"""Puerto de persistencia de AgentRun (Harness)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Optional

from core.ai.harness.schemas import AgentRunSchema, AgentRunStatus


class IAssistantAgentRunRepository(ABC):

    @abstractmethod
    def start(
        self,
        *,
        user_id: uuid.UUID,
        run_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        provider: str = '',
        model_id: str = '',
    ) -> AgentRunSchema:
        ...

    def mark_awaiting_approval(self, run_id: uuid.UUID) -> None:
        """Optional: persist HITL pause state."""
        return None

    @abstractmethod
    def finish(
        self,
        run_id: uuid.UUID,
        *,
        status: AgentRunStatus,
        conversation_id: Optional[uuid.UUID] = None,
        degraded: bool = False,
        step_count: int = 0,
        error_code: str = '',
        cancel_requested: bool = False,
    ) -> None:
        ...
