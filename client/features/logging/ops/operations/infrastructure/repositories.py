from uuid import UUID

from django.db.models import Q, QuerySet

from client.features.logging.facade.context import LogContext
from client.features.logging.ops.operations.domain.interfaces import IWarehouseEventRepository
from client.features.logging.ops.operations.domain.schemas import (
    RELATED_REFS_KEY,
    WarehouseEventInputSchema,
    WarehouseEventRecord,
)

_TRACE_FIELDS = ('id', 'event_type', 'created_at', 'zone', 'location', 'payload', 'user_id')
_RECENT_FIELDS = (
    'id', 'event_type', 'created_at', 'payload', 'reference_type', 'reference_id',
)


class DjangoWarehouseEventRepository(IWarehouseEventRepository):

    def save(self, context: LogContext, data: WarehouseEventInputSchema) -> None:
        from client.features.logging.ops.operations.models import WarehouseEvent
        WarehouseEvent.objects.create(
            event_type=data.event_type,
            zone=data.zone,
            location=data.location,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            payload=data.payload,
            user_id=context.user_id,
            warehouse_id=data.warehouse_id or context.warehouse_id,
            company_subscription_id=context.company_subscription_id,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            ip_address=context.ip_address,
        )

    def query(self, filters: dict, limit: int = 50, offset: int = 0) -> list:
        from client.features.logging.ops.operations.models import WarehouseEvent
        qs = WarehouseEvent.objects.all()
        if 'event_type' in filters:
            qs = qs.filter(event_type=filters['event_type'])
        if 'warehouse_id' in filters:
            qs = qs.filter(warehouse_id=filters['warehouse_id'])
        if 'company_subscription_id' in filters:
            qs = qs.filter(company_subscription_id=filters['company_subscription_id'])
        if 'zone' in filters:
            qs = qs.filter(zone=filters['zone'])
        if 'from_date' in filters:
            qs = qs.filter(created_at__gte=filters['from_date'])
        if 'to_date' in filters:
            qs = qs.filter(created_at__lte=filters['to_date'])
        return list(qs[offset:offset + limit])

    def list_for_reference(
        self,
        reference_id: UUID,
        reference_type: str | None,
        limit: int,
        warehouse_id: UUID | None = None,
    ) -> list[WarehouseEventRecord]:
        from client.features.logging.ops.operations.models import WarehouseEvent

        if warehouse_id is None:
            qs = WarehouseEvent.objects.filter(reference_id=str(reference_id))
            if reference_type:
                qs = qs.filter(reference_type=reference_type)
        else:
            own = Q(reference_id=str(reference_id))
            if reference_type:
                own &= Q(reference_type=reference_type)
            # ``payload @> {...}`` is served by the GIN index on payload.
            related = Q(warehouse_id=warehouse_id, payload__contains={RELATED_REFS_KEY: [str(reference_id)]})
            qs = WarehouseEvent.objects.filter(own | related)
        return self._trace_rows(qs, limit)

    def list_for_warehouse(
        self,
        warehouse_id: UUID,
        prefixes: tuple[str, ...],
        limit: int,
    ) -> list[WarehouseEventRecord]:
        from client.features.logging.ops.operations.models import WarehouseEvent

        if not prefixes:
            return []
        types = Q()
        for prefix in prefixes:
            types |= Q(event_type__startswith=prefix)
        return self._trace_rows(WarehouseEvent.objects.filter(types, warehouse_id=warehouse_id), limit)

    @staticmethod
    def _trace_rows(qs: QuerySet, limit: int) -> list[WarehouseEventRecord]:
        rows = qs.order_by('-created_at', '-id').only(*_TRACE_FIELDS)[:limit]
        return [
            WarehouseEventRecord(
                id=row.id,
                event_type=row.event_type,
                occurred_at=row.created_at,
                zone=row.zone or '',
                location=row.location or '',
                payload=row.payload if isinstance(row.payload, dict) else None,
                user_id=row.user_id,
            )
            for row in rows
        ]

    def list_recent(self, event_types: tuple[str, ...], limit: int) -> list[WarehouseEventRecord]:
        from client.features.logging.ops.operations.models import WarehouseEvent

        rows = (
            WarehouseEvent.objects.filter(event_type__in=list(event_types))
            .exclude(payload__replayed=True)
            .order_by('-created_at', '-id')
            .only(*_RECENT_FIELDS)[:limit]
        )
        return [
            WarehouseEventRecord(
                id=row.id,
                event_type=row.event_type,
                occurred_at=row.created_at,
                payload=row.payload if isinstance(row.payload, dict) else None,
                reference_type=row.reference_type or '',
                reference_id=row.reference_id or '',
            )
            for row in rows
        ]
