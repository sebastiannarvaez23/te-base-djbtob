"""Admin REST API for live logs (channels + recent buffer)."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from platform.core.authentication import AdminTokenAuthentication
from platform.features.support.ops.live_logs.application.use_cases import (
    GetRecentLiveLogsUseCase,
    ListLiveLogChannelsUseCase,
)
from platform.features.support.ops.live_logs.infrastructure.redis_ring import (
    RedisLiveLogRingBuffer,
)
from platform.features.support.ops.live_logs.presentation.queries import (
    LiveLogRecentQuery,
)

_MAX_LIMIT = 500


def _ring():
    return RedisLiveLogRingBuffer()


class LiveLogChannelsView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        result = ListLiveLogChannelsUseCase().execute()
        return wrap_response(result.model_dump(mode='json'))


class LiveLogRecentView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(LiveLogRecentQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        f = query.filters
        limit = max(1, min(int(f.get('limit', 100)), _MAX_LIMIT))
        result = GetRecentLiveLogsUseCase(_ring()).execute(
            channel=f.get('channel') or None,
            min_level=f.get('level') or None,
            limit=limit,
        )
        return wrap_response(result.model_dump(mode='json'))
