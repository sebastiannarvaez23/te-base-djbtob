"""Unit tests — AI harness evals admin use cases."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.errors import AppErrorCode, ConflictException
from core.query import PaginatedQuery

from platform.features.configuration.ai.evals.application.use_cases import (
    ListEvalSuitesUseCase,
    RunHarnessEvalsUseCase,
)
from platform.features.configuration.ai.evals.domain.schemas import (
    EvalSuiteListSchema,
    EvalSuiteOutSchema,
)


def _suite(**overrides) -> EvalSuiteOutSchema:
    base = dict(
        id=uuid4(),
        suite='harness',
        passed=1,
        failed=0,
        cases=[],
        ran_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return EvalSuiteOutSchema(**base)


@pytest.mark.unit
class TestListEvalSuitesUseCase:
    def test_paginates(self):
        repo = MagicMock()
        items = [_suite() for _ in range(3)]
        repo.list_recent.return_value = (items[:2], 3)
        repo.latest.return_value = items[0]
        result = ListEvalSuitesUseCase(repo).execute(
            PaginatedQuery(page=0, page_size=2, filters={}),
        )
        assert isinstance(result, EvalSuiteListSchema)
        assert result.total == 3
        assert len(result.items) == 2
        repo.list_recent.assert_called_once_with(offset=0, limit=2)


@pytest.mark.unit
class TestRunHarnessEvalsUseCase:
    def test_happy_path(self, monkeypatch):
        from core.ai.evals.runner import EvalSuiteResult

        repo = MagicMock()
        saved = _suite()
        repo.save.return_value = saved
        fake = EvalSuiteResult(
            id=saved.id,
            suite='harness',
            passed=1,
            failed=0,
            cases=[],
            ran_at=saved.ran_at,
        )
        monkeypatch.setattr(
            'platform.features.configuration.ai.evals.application.use_cases.run_harness_evals',
            lambda: fake,
        )
        monkeypatch.setattr(
            'platform.features.configuration.ai.evals.application.use_cases._cache',
            lambda: None,
        )
        result = RunHarnessEvalsUseCase(repo).execute()
        assert result.id == saved.id
        repo.save.assert_called_once()

    def test_concurrent_lock_raises(self, monkeypatch):
        cache = MagicMock()
        cache.add.return_value = False
        monkeypatch.setattr(
            'platform.features.configuration.ai.evals.application.use_cases._cache',
            lambda: cache,
        )
        with pytest.raises(ConflictException) as exc:
            RunHarnessEvalsUseCase(MagicMock()).execute()
        assert exc.value.code == AppErrorCode.AI_BUSY
