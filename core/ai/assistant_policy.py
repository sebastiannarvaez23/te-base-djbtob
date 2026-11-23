"""Política de runtime del assistant (agnóstica de persistencia)."""

from __future__ import annotations

from dataclasses import dataclass

from core.ai.assistant_catalog import (
    ASSISTANT_DEFAULT_HISTORY_TURNS,
    ASSISTANT_DEFAULT_MAX_AGENT_STEPS,
    ASSISTANT_DEFAULT_MAX_MESSAGE_CHARS,
    ASSISTANT_DEFAULT_OUT_OF_SCOPE,
    ASSISTANT_PROVIDERS,
    ASSISTANT_TOOL_KEYS,
)
from core.ai.config import is_ai_enabled


@dataclass(frozen=True)
class AssistantRuntimePolicy:
    enabled: bool
    provider: str
    max_message_chars: int
    max_agent_steps: int
    history_turns: int
    out_of_scope_message: str
    require_tool_before_facts: bool
    enabled_tool_keys: tuple[str, ...]

    @property
    def chat_allowed(self) -> bool:
        return is_ai_enabled() and self.enabled

    @property
    def out_of_scope_text(self) -> str:
        text = (self.out_of_scope_message or '').strip()
        return text or ASSISTANT_DEFAULT_OUT_OF_SCOPE


def default_assistant_policy() -> AssistantRuntimePolicy:
    """Defaults de entorno (sin fila en BD). Vive junto a ``is_ai_enabled``."""
    from django.conf import settings

    provider = (getattr(settings, 'AI_PROVIDER', 'fake') or 'fake').lower()
    if provider not in ASSISTANT_PROVIDERS:
        provider = 'fake'
    return AssistantRuntimePolicy(
        enabled=True,
        provider=provider,
        max_message_chars=ASSISTANT_DEFAULT_MAX_MESSAGE_CHARS,
        max_agent_steps=ASSISTANT_DEFAULT_MAX_AGENT_STEPS,
        history_turns=ASSISTANT_DEFAULT_HISTORY_TURNS,
        out_of_scope_message='',
        require_tool_before_facts=True,
        enabled_tool_keys=tuple(ASSISTANT_TOOL_KEYS),
    )
