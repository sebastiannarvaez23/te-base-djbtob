"""HookBus: puntos de extensión ordenados sin modificar el núcleo del loop."""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Optional


class HookPoint(str, Enum):
    BEFORE_RUN = 'before_run'
    BEFORE_MODEL = 'before_model'
    AFTER_MODEL = 'after_model'
    BEFORE_TOOL = 'before_tool'
    AFTER_TOOL = 'after_tool'
    ON_FINAL = 'on_final'
    ON_ERROR = 'on_error'
    ON_CANCEL = 'on_cancel'


HookFn = Callable[..., Any]


class HookBus:
    """
    Cadena determinista de hooks. Fallos en hooks se aíslan (best-effort)
    salvo que ``strict=True`` (tests).
    """

    def __init__(self, *, strict: bool = False):
        self._hooks: dict[HookPoint, list[HookFn]] = {point: [] for point in HookPoint}
        self.strict = strict

    def register(self, point: HookPoint, fn: HookFn) -> None:
        self._hooks[point].append(fn)

    def emit(self, point: HookPoint, **payload: Any) -> None:
        for fn in self._hooks[point]:
            try:
                fn(**payload)
            except Exception:
                if self.strict:
                    raise
                # Best-effort: never break the agent loop from a hook.
                continue

    def clear(self, point: Optional[HookPoint] = None) -> None:
        if point is None:
            for key in self._hooks:
                self._hooks[key].clear()
            return
        self._hooks[point].clear()
