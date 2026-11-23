"""Registro de tools del copiloto (whitelist)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

# Model-supplied args must never authorize confirmation — only the harness.
_SERVER_CONFIRM_KEYS = frozenset({'confirmed', 'confirmation', 'approved'})


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any]
    read_only: bool = True
    requires_confirmation: bool = False


@dataclass
class ToolRegistry:
    """Lista blanca de tools. El agente solo puede invocar nombres registrados."""

    _tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        if not spec.read_only and not spec.requires_confirmation:
            raise ValueError(
                f'Tool {spec.name!r} is writable and must require confirmation',
            )
        self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def catalog_for_prompt(self) -> str:
        lines = []
        for name in self.names():
            spec = self._tools[name]
            lines.append(f'- {name}: {spec.description} params={spec.parameters_schema}')
        return '\n'.join(lines)

    @staticmethod
    def _sanitize_arguments(arguments: dict[str, Any] | None) -> dict[str, Any]:
        """Strip confirmation flags the model may invent."""
        raw = dict(arguments or {})
        for key in _SERVER_CONFIRM_KEYS:
            raw.pop(key, None)
        return raw

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        confirmed: bool = False,
    ) -> Any:
        """
        Ejecuta una tool.

        ``confirmed`` is **server-only**: never read from model arguments.
        After HITL approval the agent retries with ``confirmed=True``.
        """
        spec = self.get(name)
        if spec is None:
            raise KeyError(name)
        safe_args = self._sanitize_arguments(arguments)
        if spec.requires_confirmation and not confirmed:
            raise PermissionError(
                f'Tool {name!r} requires explicit operator confirmation.',
            )
        return spec.handler(safe_args)
