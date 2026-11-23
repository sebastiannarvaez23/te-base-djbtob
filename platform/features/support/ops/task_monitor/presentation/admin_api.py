"""Admin REST API for the automated-task monitor."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from platform.core.authentication import AdminTokenAuthentication
from platform.features.support.ops.task_monitor.application.use_cases import (
    GetTaskRunLogsUseCase,
    GetTaskRunUseCase,
    ListMonitoredTasksUseCase,
    ListTaskRunsUseCase,
)
from platform.features.support.ops.task_monitor.infrastructure.repositories import (
    DjangoTaskRunRepository,
)
from platform.features.support.ops.task_monitor.presentation.queries import (
    MonitoredTaskListQuery,
    TaskRunListQuery,
)

_MAX_LIMIT = 100


def _repo():
    return DjangoTaskRunRepository()


class MonitoredTaskListView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(MonitoredTaskListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        f = query.filters
        cards = ListMonitoredTasksUseCase(_repo()).execute(
            search=f.get('search', '') or '',
            status=f.get('status', '') or '',
            group=f.get('group', '') or '',
        )
        return wrap_response({
            'items': [c.model_dump(mode='json') for c in cards],
            'total': len(cards),
        })


class TaskRunListView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(TaskRunListQuery)
    def get(self, request, task_key, *args, query: PaginatedQuery, **kwargs):
        f = query.filters
        limit = max(1, min(int(f.get('limit', 50)), _MAX_LIMIT))
        offset = max(0, int(f.get('offset', 0)))
        items, total = ListTaskRunsUseCase(_repo()).execute(
            task_key,
            status=f.get('status') or None,
            is_retry=f.get('is_retry'),
            from_date=f.get('from'),
            to_date=f.get('to'),
            limit=limit,
            offset=offset,
        )
        return wrap_response({
            'items': [i.model_dump(mode='json') for i in items],
            'total': total,
            'page': (offset // limit) + 1,
            'page_size': limit,
            'total_pages': (total + limit - 1) // limit if total else 0,
        })


class TaskRunDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, run_id, *args, **kwargs):
        run = GetTaskRunUseCase(_repo()).execute(run_id)
        return wrap_response(run.model_dump(mode='json'))


class TaskRunLogsView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, run_id, *args, **kwargs):
        logs = GetTaskRunLogsUseCase(_repo()).execute(run_id)
        return wrap_response(logs.model_dump(mode='json'))
