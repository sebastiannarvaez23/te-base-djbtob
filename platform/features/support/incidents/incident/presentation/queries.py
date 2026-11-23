from datetime import datetime

from core.query import (
    PATTERN_CODE,
    PATTERN_KEY,
    PATTERN_TEXT,
    QueryFilter,
    QueryParam,
)


class IncidentListQuery(QueryFilter):
    """Filtros admin; paginación via limit/offset (contrato existente)."""

    DATE_RANGES = (('from', 'to'),)

    code = QueryParam(coerce=str, max_length=40, pattern=PATTERN_CODE)
    status = QueryParam(
        coerce=str,
        choices=['open', 'in_progress', 'resolved', 'closed', 'discarded'],
    )
    severity = QueryParam(coerce=str, choices=['low', 'medium', 'high'])
    kind = QueryParam(coerce=str, choices=['incident', 'suggestion'])
    company = QueryParam(coerce=str, max_length=63, pattern=PATTERN_TEXT)
    module = QueryParam(coerce=str, max_length=100, pattern=PATTERN_CODE)
    functionality = QueryParam(coerce=str, max_length=100, pattern=PATTERN_KEY)
    reporter = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    from_date = QueryParam(name='from', coerce=datetime)
    to_date = QueryParam(name='to', coerce=datetime)
    limit = QueryParam(coerce=int, min_value=1)  # clamp en la vista (_MAX_LIMIT)
    offset = QueryParam(coerce=int, min_value=0)
