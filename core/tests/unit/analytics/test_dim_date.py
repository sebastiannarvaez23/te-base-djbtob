"""Unit tests for dim_date calendar builder."""

from __future__ import annotations

from datetime import date

import pytest

from core.analytics.application.dim_date import iter_dim_date_rows


@pytest.mark.unit
class TestDimDateBuilder:

    def test_builds_inclusive_range(self):
        rows = iter_dim_date_rows(date(2024, 1, 1), date(2024, 1, 3))
        assert len(rows) == 3
        assert rows[0]['date_key'] == 20240101
        assert rows[0]['full_date'] == date(2024, 1, 1)
        assert rows[0]['year'] == 2024
        assert rows[0]['month'] == 1
        assert rows[0]['day'] == 1
        assert rows[0]['day_of_week'] == 1  # Monday
        assert rows[0]['is_weekend'] is False

    def test_weekend_flag(self):
        # 2024-01-06 = Saturday
        rows = iter_dim_date_rows(date(2024, 1, 6), date(2024, 1, 7))
        assert rows[0]['is_weekend'] is True
        assert rows[1]['is_weekend'] is True

    def test_rejects_inverted_range(self):
        with pytest.raises(ValueError):
            iter_dim_date_rows(date(2024, 2, 1), date(2024, 1, 1))
