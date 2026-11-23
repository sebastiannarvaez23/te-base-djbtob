"""Relay retry policy: fixed ladder, then every 12h until the max age."""
from __future__ import annotations

from datetime import datetime, timedelta

from necore.ecosystem.backoff import ladder_delay

# 30s, 2m, 10m, 30m, 1h, 3h, 6h, 12h (then 12h repeatedly).
RETRY_LADDER_SECONDS = (30, 120, 600, 1800, 3600, 10800, 21600, 43200)
# While a void waits for its issue to land, poll on this cadence.
AWAIT_ISSUE_SECONDS = 60
# Upper bound honoured from Retry-After / breaker cooldown hints.
MAX_HINT_SECONDS = 3600


def next_delay_seconds(attempts: int, *, retry_after: float | None = None) -> float:
    """Delay before attempt ``attempts + 1`` (``attempts`` already failed)."""
    ladder = ladder_delay(attempts, RETRY_LADDER_SECONDS)
    if retry_after is not None and retry_after > 0:
        return max(ladder, min(float(retry_after), MAX_HINT_SECONDS))
    return ladder


def is_expired(created_at: datetime, now: datetime, *, max_age_hours: float) -> bool:
    return now - created_at >= timedelta(hours=max_age_hours)
