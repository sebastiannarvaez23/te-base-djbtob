"""Business-day SLA math (Mon–Fri). No holiday calendar — keep it cheap."""
from datetime import date, timedelta

_WEEKEND = {5, 6}  # Saturday, Sunday
SLA_BUSINESS_DAYS = 30


def add_business_days(start: date, days: int = SLA_BUSINESS_DAYS) -> date:
    """Return the date ``days`` weekdays after ``start`` (start itself is day 0)."""
    remaining = max(int(days), 0)
    cursor = start
    while remaining:
        cursor += timedelta(days=1)
        if cursor.weekday() not in _WEEKEND:
            remaining -= 1
    return cursor
