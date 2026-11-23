"""Re-export de la política compartida (compatibilidad client)."""

from core.ai.assistant_policy import AssistantRuntimePolicy, default_assistant_policy

__all__ = ['AssistantRuntimePolicy', 'default_assistant_policy']
