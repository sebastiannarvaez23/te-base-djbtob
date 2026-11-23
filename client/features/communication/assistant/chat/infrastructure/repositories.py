"""Persistencia del historial del asistente."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from django.db.models import Count

from core.errors import AppErrorCode, NotFoundException

from client.features.communication.assistant.chat.domain.interfaces import IAssistantConversationRepository
from client.features.communication.assistant.chat.domain.schemas import (
    ChatMessageSchema,
    ConversationSummarySchema,
)
from client.features.communication.assistant.chat.models import (
    AssistantConversation,
    AssistantMessage,
    AssistantToolCall,
)


class DjangoAssistantConversationRepository(IAssistantConversationRepository):

    def get_or_create(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> uuid.UUID:
        if conversation_id is not None:
            if not self.ensure_owned(conversation_id, user_id):
                raise NotFoundException(AppErrorCode.AI_CONVERSATION_NOT_FOUND)
            return conversation_id
        return self.create(user_id=user_id)

    def create(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> uuid.UUID:
        kwargs: dict[str, Any] = {'user_id': user_id}
        if conversation_id is not None:
            kwargs['id'] = conversation_id
        conv = AssistantConversation.objects.create(**kwargs)
        return conv.id

    def ensure_owned(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return AssistantConversation.objects.filter(
            id=conversation_id,
            user_id=user_id,
        ).exists()

    def add_message(
        self,
        conversation_id: uuid.UUID,
        *,
        role: str,
        content: str,
    ) -> ChatMessageSchema:
        try:
            conv = AssistantConversation.objects.get(id=conversation_id)
        except AssistantConversation.DoesNotExist as exc:
            raise NotFoundException(AppErrorCode.AI_CONVERSATION_NOT_FOUND) from exc
        msg = AssistantMessage.objects.create(
            conversation=conv,
            role=role,
            content=content,
        )
        from django.utils import timezone
        AssistantConversation.objects.filter(id=conversation_id).update(
            updated_at=timezone.now(),
        )
        return ChatMessageSchema(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
        )

    def list_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 40,
    ) -> list[ChatMessageSchema]:
        qs = (
            AssistantMessage.objects
            .filter(conversation_id=conversation_id)
            .order_by('-created_at')[:limit]
        )
        rows = list(reversed(list(qs)))
        return [
            ChatMessageSchema(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in rows
        ]

    def list_conversations(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 20,
        q: Optional[str] = None,
    ) -> list[ConversationSummarySchema]:
        qs = (
            AssistantConversation.objects
            .filter(user_id=user_id)
            .annotate(message_count=Count('messages'))
            .order_by('-updated_at')
        )
        if q:
            qs = qs.filter(title__icontains=q)
        qs = qs[:limit]
        return [self._to_summary(c) for c in qs]

    def get_summary(self, conversation_id: uuid.UUID) -> Optional[ConversationSummarySchema]:
        conv = (
            AssistantConversation.objects
            .filter(id=conversation_id)
            .annotate(message_count=Count('messages'))
            .first()
        )
        if conv is None:
            return None
        return self._to_summary(conv)

    def touch_title(self, conversation_id: uuid.UUID, title: str) -> None:
        cleaned = (title or '').strip()[:200]
        if cleaned:
            AssistantConversation.objects.filter(id=conversation_id).update(title=cleaned)

    @staticmethod
    def _to_summary(c: AssistantConversation) -> ConversationSummarySchema:
        return ConversationSummarySchema(
            id=c.id,
            title=c.title or '',
            updated_at=c.updated_at,
            message_count=getattr(c, 'message_count', 0),
        )

    def record_tool_call(
        self,
        conversation_id: uuid.UUID,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        result_preview: str,
        success: bool,
        error_code: str = '',
        message_id: Optional[uuid.UUID] = None,
    ) -> None:
        AssistantToolCall.objects.create(
            conversation_id=conversation_id,
            message_id=message_id,
            tool_name=tool_name,
            arguments=arguments or {},
            result_preview=(result_preview or '')[:4000],
            success=success,
            error_code=error_code or '',
        )

    def save_turn(
        self,
        conversation_id: uuid.UUID,
        *,
        user_text: str,
        reply: str,
        tool_audits: list,
        pending_title: Optional[str] = None,
    ) -> ChatMessageSchema:
        from django.db import transaction

        with transaction.atomic():
            self.add_message(conversation_id, role='user', content=user_text)
            if pending_title:
                self.touch_title(conversation_id, pending_title)
            assistant_msg = self.add_message(conversation_id, role='assistant', content=reply)
            for audit in tool_audits:
                self.record_tool_call(
                    conversation_id,
                    tool_name=audit['tool_name'],
                    arguments=audit.get('arguments') or {},
                    result_preview=audit.get('result_preview') or '',
                    success=bool(audit.get('success', True)),
                    error_code=audit.get('error_code') or '',
                    message_id=assistant_msg.id,
                )
            return assistant_msg
