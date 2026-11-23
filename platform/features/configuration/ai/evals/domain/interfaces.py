from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.ai.evals import EvalSuiteResult

from .schemas import EvalSuiteOutSchema


class IEvalSuiteRepository(ABC):

    @abstractmethod
    def save(self, result: EvalSuiteResult) -> EvalSuiteOutSchema:
        ...

    @abstractmethod
    def list_recent(self, *, offset: int, limit: int) -> tuple[list[EvalSuiteOutSchema], int]:
        ...

    @abstractmethod
    def latest(self) -> Optional[EvalSuiteOutSchema]:
        ...
