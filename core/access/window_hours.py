"""Constantes y coerción de duración de ventana de cupo (1–168 h)."""

WINDOW_HOURS_MIN = 1
WINDOW_HOURS_MAX = 168


def coerce_window_hours(window_hours) -> int:
    """Retorna horas válidas o lanza ValueError (sin default a 1 h)."""
    if window_hours is None:
        raise ValueError('window_hours is required')
    try:
        hours = int(window_hours)
    except (TypeError, ValueError) as exc:
        raise ValueError('window_hours must be an integer') from exc
    if hours < WINDOW_HOURS_MIN or hours > WINDOW_HOURS_MAX:
        raise ValueError(
            f'window_hours must be between {WINDOW_HOURS_MIN} and {WINDOW_HOURS_MAX}',
        )
    return hours
