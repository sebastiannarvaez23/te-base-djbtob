from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from client.features.logging.ops.operations.application.use_cases import (
    ListRecentActivityUseCase,
    ListRecordTraceUseCase,
    ListScopeTraceUseCase,
)
from client.features.logging.ops.operations.domain.schemas import RECENT_ACTIVITY_LIMIT, TraceScope
from client.features.logging.ops.operations.infrastructure.actor_directory import (
    DjangoActorDirectory,
)
from client.features.logging.ops.operations.infrastructure.repositories import (
    DjangoWarehouseEventRepository,
)
from client.features.logging.ops.operations.presentation.queries import (
    RecentActivityQuery,
    RecordTraceQuery,
)
from core.decorators.response import wrap_response
from core.permissions import IsCompanyMember
from core.query import validated_query


def _use_case() -> ListRecordTraceUseCase:
    return ListRecordTraceUseCase(DjangoWarehouseEventRepository(), DjangoActorDirectory())


def _scope_use_case() -> ListScopeTraceUseCase:
    return ListScopeTraceUseCase(DjangoWarehouseEventRepository(), DjangoActorDirectory())


def _activity_use_case() -> ListRecentActivityUseCase:
    return ListRecentActivityUseCase(DjangoWarehouseEventRepository())


class RecentActivityView(APIView):
    """Últimos hitos de la operación para el toolbar."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_query(RecentActivityQuery)
    def get(self, request, *, query, **kwargs):
        entries = _activity_use_case().execute(query.filters.get('limit', RECENT_ACTIVITY_LIMIT))
        return wrap_response(
            {'items': [item.model_dump(mode='json') for item in entries]},
            message='Recent activity loaded.',
        )


class RecordTraceView(APIView):
    """Movimientos de bodega del registro seleccionado en el módulo."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_query(RecordTraceQuery)
    def get(self, request, *, query, **kwargs):
        filters = query.filters
        warehouse_id = UUID(filters['warehouse_id']) if filters.get('warehouse_id') else None
        if filters.get('scope'):
            entries = _scope_use_case().execute(warehouse_id, TraceScope(filters['scope']))
        else:
            entries = _use_case().execute(
                UUID(filters['reference_id']),
                filters.get('reference_type'),
                warehouse_id,
            )
        return wrap_response(
            {'items': [item.model_dump(mode='json') for item in entries]},
            message='Record trace loaded.',
        )
