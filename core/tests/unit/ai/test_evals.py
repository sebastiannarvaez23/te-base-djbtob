"""Unit tests — harness eval suite."""

from __future__ import annotations

import pytest

from core.ai.evals import run_harness_evals


@pytest.mark.unit
def test_harness_evals_all_pass():
    result = run_harness_evals()
    assert result.failed == 0
    assert result.passed == len(result.cases)
    assert result.suite == 'harness'
