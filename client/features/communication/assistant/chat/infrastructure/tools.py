"""Registro de tools del asistente.

El template no trae tools de producto. Un dominio nuevo registra las suyas
en ``build_default_tool_registry``.
"""

from __future__ import annotations

from client.features.communication.assistant.chat.domain.tool_registry import ToolRegistry


def build_default_tool_registry(
    enabled_keys: tuple[str, ...] | list[str] | None = None,
) -> ToolRegistry:
    return ToolRegistry()
