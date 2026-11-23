from uuid import UUID

from client.features.logging.facade.context import LogContext
from client.features.logging.ops.operations.domain.activity import (
    build_activity_entry,
    dedupe_milestones,
    is_milestone,
)
from client.features.logging.ops.operations.domain.interfaces import (
    IActorDirectory,
    IWarehouseEventRepository,
)
from client.features.logging.ops.operations.domain.schemas import (
    RECENT_ACTIVITY_EVENT_TYPES,
    RECENT_ACTIVITY_LIMIT,
    RECORD_TRACE_LIMIT,
    TRACE_SCOPE_PREFIXES,
    RecentActivityEntry,
    RecordTraceEntry,
    TraceScope,
    WarehouseEventInputSchema,
    WarehouseEventRecord,
)
from client.features.logging.ops.operations.domain.trace import build_trace_entry
from core.trace import trace_layer


class RegisterWarehouseEventUseCase:
    def __init__(self, repository: IWarehouseEventRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, context: LogContext, data: WarehouseEventInputSchema) -> None:
        self.repository.save(context, data)


class QueryWarehouseEventsUseCase:
    def __init__(self, repository: IWarehouseEventRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        return self.repository.query(filters, limit, offset)


class ListRecordTraceUseCase:
    """Trazabilidad del registro que el operario tiene seleccionado."""

    def __init__(self, repository: IWarehouseEventRepository, actors: IActorDirectory):
        self.repository = repository
        self.actors = actors

    @trace_layer('application')
    def execute(
        self,
        reference_id: UUID,
        reference_type: str | None = None,
        warehouse_id: UUID | None = None,
    ) -> list[RecordTraceEntry]:
        records = self.repository.list_for_reference(
            reference_id, reference_type or None, RECORD_TRACE_LIMIT, warehouse_id,
        )
        return _trace_entries(records, self.actors)


class ListScopeTraceUseCase:
    """Historia de una superficie del almacén (plano, red de recorrido)."""

    def __init__(self, repository: IWarehouseEventRepository, actors: IActorDirectory):
        self.repository = repository
        self.actors = actors

    @trace_layer('application')
    def execute(self, warehouse_id: UUID, scope: TraceScope) -> list[RecordTraceEntry]:
        records = self.repository.list_for_warehouse(
            warehouse_id, TRACE_SCOPE_PREFIXES[scope], RECORD_TRACE_LIMIT,
        )
        return _trace_entries(records, self.actors)


def _trace_entries(records: list[WarehouseEventRecord], actors: IActorDirectory) -> list[RecordTraceEntry]:
    names = actors.display_names({r.user_id for r in records if r.user_id})
    return [build_trace_entry(r, names.get(r.user_id, '')) for r in records]


class ListRecentActivityUseCase:
    """Últimos hitos de piso del tenant, sin eventos de línea ni reintentos."""

    # Margen para que los duplicados descartados no vacíen el panel.
    OVERFETCH = 2

    def __init__(self, repository: IWarehouseEventRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, limit: int = RECENT_ACTIVITY_LIMIT) -> list[RecentActivityEntry]:
        bounded = limit if 1 <= limit <= RECENT_ACTIVITY_LIMIT else RECENT_ACTIVITY_LIMIT
        records = self.repository.list_recent(
            RECENT_ACTIVITY_EVENT_TYPES, bounded * self.OVERFETCH,
        )
        entries = [build_activity_entry(r) for r in records if is_milestone(r)]
        return dedupe_milestones(entries)[:bounded]
