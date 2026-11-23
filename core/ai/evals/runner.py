"""Runner de evals del harness (sin proveedor externo)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from core.ids import uuid7

from .cases import HARNESS_EVAL_CASES


class EvalCaseResult(BaseModel):
    key: str
    description: str
    passed: bool
    detail: str = ''


class EvalSuiteResult(BaseModel):
    id: UUID = Field(default_factory=uuid7)
    suite: str = 'harness'
    passed: int = 0
    failed: int = 0
    cases: list[EvalCaseResult] = Field(default_factory=list)
    ran_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def run_harness_evals() -> EvalSuiteResult:
    cases: list[EvalCaseResult] = []
    for case in HARNESS_EVAL_CASES:
        try:
            ok = bool(case.run())
            cases.append(EvalCaseResult(
                key=case.key,
                description=case.description,
                passed=ok,
                detail='' if ok else 'assertion failed',
            ))
        except Exception as exc:
            cases.append(EvalCaseResult(
                key=case.key,
                description=case.description,
                passed=False,
                detail=str(exc)[:500],
            ))
    passed = sum(1 for c in cases if c.passed)
    failed = len(cases) - passed
    return EvalSuiteResult(passed=passed, failed=failed, cases=cases)
