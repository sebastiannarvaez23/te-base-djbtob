"""ORM adapter for AssistantAgentRun."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from django.utils import timezone

from core.ai.harness.schemas import AgentRunSchema, AgentRunStatus
from core.ids import uuid7

from client.features.communication.assistant.chat.domain.run_interfaces import IAssistantAgentRunRepository
from client.features.communication.assistant.chat.models import AssistantAgentRun

logger = logging.getLogger('app.ai')


class DjangoAssistantAgentRunRepository(IAssistantAgentRunRepository):

    def start(
        self,
        *,
        user_id: uuid.UUID,
        run_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        provider: str = '',
        model_id: str = '',
    ) -> AgentRunSchema:
        rid = run_id or uuid7()
        now = timezone.now()
        row = AssistantAgentRun.objects.create(
            id=rid,
            user_id=user_id,
            conversation_id=conversation_id,
            status=AssistantAgentRun.Status.RUNNING,
            provider=(provider or '')[:40],
            model_id=(model_id or '')[:120],
            started_at=now,
        )
        return AgentRunSchema(
            id=row.id,
            conversation_id=row.conversation_id,
            user_id=row.user_id,
            status='running',
            provider=row.provider,
            model_id=row.model_id,
            started_at=row.started_at,
        )

    def mark_awaiting_approval(self, run_id: uuid.UUID) -> None:
        updated = AssistantAgentRun.objects.filter(id=run_id).update(
            status=AssistantAgentRun.Status.AWAITING_APPROVAL,
        )
        if not updated:
            logger.warning('agent run awaiting_approval missing id=%s', run_id)

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
        updates = {
            'status': status,
            'degraded': degraded,
            'step_count': max(0, int(step_count)),
            'error_code': (error_code or '')[:40],
            'cancel_requested': cancel_requested,
            'finished_at': timezone.now(),
        }
        if conversation_id is not None:
            updates['conversation_id'] = conversation_id
        updated = AssistantAgentRun.objects.filter(id=run_id).update(**updates)
        if not updated:
            logger.warning('agent run finish missing id=%s status=%s', run_id, status)
