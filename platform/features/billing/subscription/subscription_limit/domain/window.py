"""Invariante de dominio: tipo window exige hours 1–168; el resto no lleva hours."""

from typing import Optional

WINDOW_HOURS_MIN = 1
WINDOW_HOURS_MAX = 168
VALIDATION_TYPES = ('daily', 'lifetime', 'window')


class WindowHoursError(ValueError):
    """Invariante de ventana incumplido."""


def resolved_window_hours(
    validation_type: str,
    window_hours: Optional[int],
    *,
    require_if_window: bool,
) -> Optional[int]:
    if validation_type not in VALIDATION_TYPES:
        raise WindowHoursError(f'Invalid validation_type: {validation_type}')
    if validation_type != 'window':
        return None
    if window_hours is None:
        if require_if_window:
            raise WindowHoursError("window_hours is required when validation_type is 'window'")
        return None
    hours = int(window_hours)
    if hours < WINDOW_HOURS_MIN or hours > WINDOW_HOURS_MAX:
        raise WindowHoursError(
            f'window_hours must be between {WINDOW_HOURS_MIN} and {WINDOW_HOURS_MAX}',
        )
    return hours
