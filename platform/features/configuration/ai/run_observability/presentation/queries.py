from core.query import QueryFilter, QueryParam


class AgentRunListQuery(QueryFilter):
    """GET /platform/ai/runs/ — siempre paginado."""

    ALLOW_UNPAGINATED = False

    status = QueryParam(
        coerce=str,
        required=False,
        max_length=32,
        choices=[
            'queued', 'running', 'awaiting_approval', 'streaming',
            'completed', 'cancelled', 'failed', 'degraded',
        ],
    )
