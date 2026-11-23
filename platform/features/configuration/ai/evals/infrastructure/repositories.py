from __future__ import annotations

import logging
from typing import Optional

from core.ai.evals import EvalSuiteResult

from platform.features.configuration.ai.evals.domain.interfaces import IEvalSuiteRepository
from platform.features.configuration.ai.evals.domain.schemas import (
    EvalCaseOutSchema,
    EvalSuiteOutSchema,
)
from platform.features.configuration.ai.evals.models import AiEvalSuiteRun

logger = logging.getLogger('app.ai')


def _to_schema(row: AiEvalSuiteRun) -> EvalSuiteOutSchema:
    cases = []
    for item in row.cases or []:
        try:
            cases.append(EvalCaseOutSchema.model_validate(item))
        except Exception as exc:
            logger.warning('eval suite case corrupt suite=%s: %s', row.id, exc)
            continue
    return EvalSuiteOutSchema(
        id=row.id,
        suite=row.suite,
        passed=row.passed,
        failed=row.failed,
        cases=cases,
        ran_at=row.ran_at,
    )


class DjangoEvalSuiteRepository(IEvalSuiteRepository):

    def save(self, result: EvalSuiteResult) -> EvalSuiteOutSchema:
        row = AiEvalSuiteRun.objects.create(
            id=result.id,
            suite=result.suite,
            passed=result.passed,
            failed=result.failed,
            cases=[c.model_dump(mode='json') for c in result.cases],
            ran_at=result.ran_at,
        )
        return _to_schema(row)

    def list_recent(self, *, offset: int, limit: int) -> tuple[list[EvalSuiteOutSchema], int]:
        qs = AiEvalSuiteRun.objects.all().order_by('-ran_at')
        total = qs.count()
        rows = list(qs[offset:offset + limit])
        return [_to_schema(r) for r in rows], total

    def latest(self) -> Optional[EvalSuiteOutSchema]:
        row = AiEvalSuiteRun.objects.order_by('-ran_at').first()
        return _to_schema(row) if row else None
