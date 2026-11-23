import re

from client.features.logging.ops.operations.domain.schemas import (
    RecordTraceEntry,
    WarehouseEventRecord,
)

_UUID = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)
_DETAIL_KEYS = ('number', 'code', 'sku')
_DETAIL_MAX_LENGTH = 80


def build_trace_entry(record: WarehouseEventRecord, actor_name: str = '') -> RecordTraceEntry:
    return RecordTraceEntry(
        id=record.id,
        event_type=record.event_type.strip(),
        occurred_at=record.occurred_at,
        zone=record.zone.strip(),
        location=record.location.strip(),
        detail=readable_detail(record.payload),
        actor_name=actor_name.strip(),
    )


def readable_detail(payload: dict | None) -> str:
    """Códigos legibles del payload; nunca UUIDs ni textos largos."""
    if not payload:
        return ''
    parts: list[str] = []
    for key in _DETAIL_KEYS:
        value = payload.get(key)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or _UUID.fullmatch(text) or len(text) > _DETAIL_MAX_LENGTH:
            continue
        parts.append(text)
    return ' · '.join(parts)
