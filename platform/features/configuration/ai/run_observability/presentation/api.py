from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.ai.run_observability.application.use_cases import (
    ListAgentRunsAdminUseCase,
)
from platform.features.configuration.ai.run_observability.infrastructure.probes import (
    TenantAgentRunProbe,
)
from platform.features.configuration.ai.run_observability.presentation.queries import (
    AgentRunListQuery,
)


class AgentRunListView(APIView):
    """``GET /api/v1/platform/ai/runs/`` — lista paginada de AgentRuns."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(AgentRunListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = ListAgentRunsAdminUseCase(TenantAgentRunProbe()).execute(query)
        return wrap_response(result.model_dump(mode='json'))
