"""Carga la política persistida (plataforma) para REST y WebSocket."""

from __future__ import annotations

from client.features.communication.assistant.chat.domain.runtime import AssistantRuntimePolicy
from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry
from client.features.communication.assistant.chat.infrastructure.tools import build_default_tool_registry


def load_chat_runtime() -> tuple[AssistantRuntimePolicy, ToolRegistry]:
    from platform.features.configuration.assistant.assistant.application.use_cases import (
        LoadAssistantRuntimePolicyUseCase,
    )
    from platform.features.configuration.assistant.assistant.infrastructure.repositories import (
        DjangoAssistantSettingsRepository,
    )

    policy = LoadAssistantRuntimePolicyUseCase(
        DjangoAssistantSettingsRepository(),
    ).execute()
    registry = build_default_tool_registry(enabled_keys=policy.enabled_tool_keys)
    return policy, registry
