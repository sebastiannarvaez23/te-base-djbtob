from core.query import QueryFilter, QueryParam

from platform.features.communication.messaging.inbox.domain.enums import (
    AudienceScope,
    OutboxStatus,
    ReadStatus,
)


class OutboxQuery(QueryFilter):
    status = QueryParam(coerce=str, choices=[s.value for s in OutboxStatus])
    scope = QueryParam(coerce=str, choices=[s.value for s in AudienceScope])


class ResourceTypeListQuery(QueryFilter):
    only_active = QueryParam(coerce=bool)


class AdminInboxQuery(QueryFilter):
    status = QueryParam(coerce=str, choices=[s.value for s in ReadStatus])
