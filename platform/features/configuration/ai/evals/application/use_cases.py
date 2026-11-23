from __future__ import annotations

import logging

from django.core.cache import caches

from core.ai.evals import run_harness_evals
from core.errors import AppErrorCode, ConflictException
from core.query import PaginatedQuery
from core.trace import trace_layer

from platform.features.configuration.ai.evals.domain.interfaces import IEvalSuiteRepository
from platform.features.configuration.ai.evals.domain.schemas import (
    EvalSuiteListSchema,
    EvalSuiteOutSchema,
)

logger = logging.getLogger('app.ai')

_EVAL_LOCK_KEY = 'ai:evals:run:lock'
_EVAL_LOCK_TTL = 300  # seconds — hard cap for a suite run


def _cache():
    try:
        return caches['access']
    except Exception:
        return None


class RunHarnessEvalsUseCase:
    def __init__(self, repository: IEvalSuiteRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self) -> EvalSuiteOutSchema:
        cache = _cache()
        lock_owned = False
        if cache is not None:
            try:
                lock_owned = bool(cache.add(_EVAL_LOCK_KEY, '1', timeout=_EVAL_LOCK_TTL))
            except Exception as exc:
                logger.warning('evals lock acquire failed (fail-open): %s', exc)
                lock_owned = False
            else:
                if not lock_owned:
                    raise ConflictException(
                        AppErrorCode.AI_BUSY,
                        override_detail='An AI eval suite is already running. Try again later.',
                    )
        try:
            result = run_harness_evals()
            return self.repository.save(result)
        finally:
            if cache is not None and lock_owned:
                try:
                    cache.delete(_EVAL_LOCK_KEY)
                except Exception as exc:
                    logger.debug('evals lock release failed: %s', exc)


class ListEvalSuitesUseCase:
    def __init__(self, repository: IEvalSuiteRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> EvalSuiteListSchema:
        items, total = self.repository.list_recent(
            offset=query.offset, limit=query.limit,
        )
        return EvalSuiteListSchema(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            latest=self.repository.latest(),
        )
