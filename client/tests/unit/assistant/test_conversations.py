"""Unit tests — historial y rename de conversaciones del assistant."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from core.errors import AppErrorCode, NotFoundException, ValidationAppException

from client.features.communication.assistant.chat.application.use_cases import (
    GetConversationMessagesUseCase,
    RenameConversationUseCase,
)
from client.features.communication.assistant.chat.domain.schemas import ConversationSummarySchema


class MemoryConversationRepo:
    def __init__(self):
        self.conversations = {}
        self.titles = {}
        self.updated_at = {}
        self.messages = {}

    def ensure_owned(self, conversation_id, user_id):
        return self.conversations.get(conversation_id) == user_id

    def touch_title(self, conversation_id, title):
        self.titles[conversation_id] = (title or '').strip()[:200]

    def get_summary(self, conversation_id):
        if conversation_id not in self.conversations:
            return None
        return ConversationSummarySchema(
            id=conversation_id,
            title=self.titles.get(conversation_id, ''),
            updated_at=self.updated_at.get(conversation_id, datetime.now(timezone.utc)),
            message_count=0,
        )

    def list_messages(self, conversation_id, *, limit=100):
        return self.messages.get(conversation_id, [])[:limit]


@pytest.mark.unit
class TestRenameConversationUseCase:

    def setup_method(self):
        self.user_id = uuid.uuid4()
        self.other_id = uuid.uuid4()
        self.conv_id = uuid.uuid4()
        self.repo = MemoryConversationRepo()
        self.repo.conversations[self.conv_id] = self.user_id
        self.repo.titles[self.conv_id] = 'Pedido ORD-0001'
        self.use_case = RenameConversationUseCase(self.repo)

    def test_renames_owned_conversation(self):
        result = self.use_case.execute(
            user_id=self.user_id,
            conversation_id=self.conv_id,
            title='  Inventario de zona A  ',
        )
        assert result.id == self.conv_id
        assert result.title == 'Inventario de zona A'
        assert self.repo.titles[self.conv_id] == 'Inventario de zona A'

    def test_rejects_blank_title(self):
        with pytest.raises(ValidationAppException) as ctx:
            self.use_case.execute(
                user_id=self.user_id,
                conversation_id=self.conv_id,
                title='   ',
            )
        assert ctx.value.code == AppErrorCode.VALIDATION_ERROR
        assert self.repo.titles[self.conv_id] == 'Pedido ORD-0001'

    def test_missing_conversation_is_not_found(self):
        with pytest.raises(NotFoundException) as ctx:
            self.use_case.execute(
                user_id=self.user_id,
                conversation_id=uuid.uuid4(),
                title='Otro nombre',
            )
        assert ctx.value.code == AppErrorCode.AI_CONVERSATION_NOT_FOUND

    def test_foreign_conversation_is_not_found(self):
        with pytest.raises(NotFoundException) as ctx:
            self.use_case.execute(
                user_id=self.other_id,
                conversation_id=self.conv_id,
                title='Hack',
            )
        assert ctx.value.code == AppErrorCode.AI_CONVERSATION_NOT_FOUND
        assert self.repo.titles[self.conv_id] == 'Pedido ORD-0001'


@pytest.mark.unit
class TestGetConversationMessagesUseCase:

    def setup_method(self):
        self.user_id = uuid.uuid4()
        self.other_id = uuid.uuid4()
        self.conv_id = uuid.uuid4()
        self.repo = MemoryConversationRepo()
        self.repo.conversations[self.conv_id] = self.user_id
        self.use_case = GetConversationMessagesUseCase(self.repo)

    def test_foreign_conversation_is_not_found(self):
        with pytest.raises(NotFoundException) as ctx:
            self.use_case.execute(
                user_id=self.other_id,
                conversation_id=self.conv_id,
            )
        assert ctx.value.code == AppErrorCode.AI_CONVERSATION_NOT_FOUND
