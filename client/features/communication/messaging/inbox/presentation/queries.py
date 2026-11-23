from core.query import QueryFilter, QueryParam

from client.features.communication.messaging.inbox.domain.enums import ReadStatus


class InboxQuery(QueryFilter):
    status = QueryParam(coerce=str, choices=[s.value for s in ReadStatus])
