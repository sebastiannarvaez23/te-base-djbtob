from datetime import datetime

from core.query import PATTERN_TEXT, QueryFilter, QueryParam

from platform.features.support.sessions.session.models import SupportSession

_STATUSES = [c[0] for c in SupportSession.STATUS_CHOICES]


class SupportSessionListQuery(QueryFilter):
    DATE_RANGES = (('from', 'to'),)

    status = QueryParam(coerce=str, choices=_STATUSES)
    company = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    search = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    from_date = QueryParam(name='from', coerce=datetime)
    to_date = QueryParam(name='to', coerce=datetime)


class SupportSessionMessagesQuery(QueryFilter):
    """Paginated message history for a session."""


class SupportSessionEventsQuery(QueryFilter):
    """Paginated event timeline for a session."""
