"""Hitos de operación para el panel de actividad reciente."""

from client.features.logging.ops.operations.domain.schemas import (
    ACTIVITY_COUNT_MAX,
    RECENT_ACTIVITY_EVENT_TYPES,
    RecentActivityEntry,
    WarehouseEventRecord,
)
from client.features.logging.ops.operations.domain.trace import readable_detail

_COUNT_KEYS = ('task_count', 'lines_count')
_MILESTONES = frozenset(RECENT_ACTIVITY_EVENT_TYPES)


def is_milestone(record: WarehouseEventRecord) -> bool:
    """Hito de documento real: tipo permitido y no un reintento idempotente."""
    if record.event_type not in _MILESTONES:
        return False
    return not (isinstance(record.payload, dict) and record.payload.get('replayed') is True)


def build_activity_entry(record: WarehouseEventRecord) -> RecentActivityEntry:
    return RecentActivityEntry(
        id=record.id,
        event_type=record.event_type.strip(),
        occurred_at=record.occurred_at,
        detail=readable_detail(record.payload),
        reference_type=record.reference_type.strip(),
        reference_id=record.reference_id.strip(),
        count=activity_count(record.payload),
    )


def activity_count(payload: dict | None) -> int | None:
    """Cantidad operativa (tareas o líneas). Nunca un identificador."""
    if not isinstance(payload, dict):
        return None
    for key in _COUNT_KEYS:
        value = payload.get(key)
        if type(value) is int and 0 <= value <= ACTIVITY_COUNT_MAX:
            return value
    return None


def dedupe_milestones(entries: list[RecentActivityEntry]) -> list[RecentActivityEntry]:
    """Quita repeticiones del mismo hito (mismo documento y detalle), conservando el más reciente."""
    seen: set[tuple[str, str, str]] = set()
    unique: list[RecentActivityEntry] = []
    for entry in entries:
        key = (entry.event_type, entry.reference_id, entry.detail)
        if entry.reference_id and key in seen:
            continue
        seen.add(key)
        unique.append(entry)
    return unique
