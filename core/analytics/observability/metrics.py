"""Contadores básicos de analytics (memoria; extensible)."""

from __future__ import annotations

from collections import Counter

_counts: Counter[str] = Counter()


def increment(metric: str, value: int = 1) -> None:
    _counts[metric] += value


def snapshot() -> dict[str, int]:
    return dict(_counts)


def reset_metrics() -> None:
    """Solo para tests."""
    _counts.clear()
