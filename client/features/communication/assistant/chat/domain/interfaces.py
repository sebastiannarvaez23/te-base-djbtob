"""Puertos del asistente."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional

from .schemas import ChatMessageSchema, ConversationSummarySchema


class IAssistantConversationRepository(ABC):

    @abstractmethod
    def get_or_create(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> uuid.UUID:
        ...

    @abstractmethod
    def create(
        self,
        *,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> uuid.UUID:
        """Persist a new conversation row (optional explicit uuid7 id)."""
        ...

    @abstractmethod
    def ensure_owned(self, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        ...

    @abstractmethod
    def add_message(
        self,
        conversation_id: uuid.UUID,
        *,
        role: str,
        content: str,
    ) -> ChatMessageSchema:
        ...

    @abstractmethod
    def list_messages(
        self,
        conversation_id: uuid.UUID,
        *,
        limit: int = 40,
    ) -> list[ChatMessageSchema]:
        ...

    @abstractmethod
    def list_conversations(
        self,
        user_id: uuid.UUID,
        *,
        limit: int = 20,
        q: Optional[str] = None,
    ) -> list[ConversationSummarySchema]:
        ...

    @abstractmethod
    def get_summary(self, conversation_id: uuid.UUID) -> Optional[ConversationSummarySchema]:
        ...

    @abstractmethod
    def touch_title(self, conversation_id: uuid.UUID, title: str) -> None:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    def save_turn(
        self,
        conversation_id: uuid.UUID,
        *,
        user_text: str,
        reply: str,
        tool_audits: list[dict[str, Any]],
        pending_title: Optional[str] = None,
    ) -> ChatMessageSchema:
        """
        Persist user + assistant + tool audits atomically when using ORM.

        Returns the assistant message schema.
        """
        ...
