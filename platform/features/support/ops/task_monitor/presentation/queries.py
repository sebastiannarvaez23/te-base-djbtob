from datetime import datetime

from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class MonitoredTaskListQuery(QueryFilter):
    search = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status = QueryParam(
        coerce=str,
        choices=['pending', 'running', 'success', 'failed', 'skipped'],
    )
    group = QueryParam(coerce=str, choices=['onboarding', 'company', 'billing'])


class TaskRunListQuery(QueryFilter):
    DATE_RANGES = (('from', 'to'),)

    status = QueryParam(
        coerce=str,
        choices=['pending', 'running', 'success', 'failed', 'skipped'],
    )
    is_retry = QueryParam(coerce=bool)
    from_date = QueryParam(name='from', coerce=datetime)
    to_date = QueryParam(name='to', coerce=datetime)
    limit = QueryParam(coerce=int, min_value=1)  # clamp en la vista (_MAX_LIMIT)
    offset = QueryParam(coerce=int, min_value=0)
