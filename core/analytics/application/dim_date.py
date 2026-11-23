"""Build calendar rows for dw.dim_date (no Django seed in migrations)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def iter_dim_date_rows(start: date, end: date) -> list[dict[str, Any]]:
    if end < start:
        raise ValueError('end date must be >= start date')
    rows: list[dict[str, Any]] = []
    current = start
    one = timedelta(days=1)
    while current <= end:
        iso = current.isocalendar()
        rows.append({
            'date_key': int(current.strftime('%Y%m%d')),
            'full_date': current,
            'year': current.year,
            'quarter': (current.month - 1) // 3 + 1,
            'month': current.month,
            'day': current.day,
            'week_iso': iso.week,
            'day_of_week': iso.weekday,  # Mon=1 .. Sun=7
            'is_weekend': iso.weekday >= 6,
        })
        current += one
    return rows
