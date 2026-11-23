from core.query import QueryFilter, QueryParam
from platform.features.support.ops.live_logs.domain.catalog import (
    LEVEL_CHOICES,
    all_channel_keys,
)


class LiveLogRecentQuery(QueryFilter):
    channel = QueryParam(coerce=str, choices=list(all_channel_keys()))
    min_level = QueryParam(name='level', coerce=str, choices=list(LEVEL_CHOICES))
    limit = QueryParam(coerce=int, min_value=1, max_value=500)
