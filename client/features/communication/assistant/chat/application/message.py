"""Normalización / gate de mensaje del chat (REST + stream)."""

from __future__ import annotations

from core.ai.assistant_policy import AssistantRuntimePolicy
from core.errors import AppErrorCode, ServerException, ValidationAppException


def normalize_chat_message(policy: AssistantRuntimePolicy, message: str) -> str:
    if not policy.chat_allowed:
        raise ServerException(AppErrorCode.AI_DISABLED)

    text = (message or '').strip()
    if not text:
        raise ValidationAppException(
            AppErrorCode.VALIDATION_ERROR,
            override_detail='Message cannot be empty.',
        )
    if len(text) > policy.max_message_chars:
        raise ValidationAppException(
            AppErrorCode.VALIDATION_ERROR,
            override_detail='Message exceeds the configured character limit.',
        )
    return text
