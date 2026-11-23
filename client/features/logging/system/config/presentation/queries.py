from core.query import QueryFilter, QueryParam


class LogConfigListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    log_type = QueryParam(
        coerce=str,
        choices=[
            'audit',
            'operations',
            'integration',
            'security',
            'errors',
            'performance',
            'system',
            'tenant',
        ],
    )
    enabled = QueryParam(coerce=bool)
