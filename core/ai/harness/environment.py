"""CapabilityBoundary: el modelo solo alcanza tools de una allow-list."""

from __future__ import annotations

from typing import FrozenSet, Iterable


class CapabilityBoundary:
    """
    Deny-by-default: sin shell, filesystem ni HTTP arbitrario.
    Solo nombres de tool explícitamente permitidos para el run.
    """

    def __init__(self, allowed_tool_keys: Iterable[str] | None = None):
        self._allowed: FrozenSet[str] = frozenset(allowed_tool_keys or ())

    @property
    def allowed_tool_keys(self) -> FrozenSet[str]:
        return self._allowed

    def allows(self, tool_name: str) -> bool:
        return tool_name in self._allowed

    def with_tools(self, keys: Iterable[str]) -> 'CapabilityBoundary':
        return CapabilityBoundary(keys)
