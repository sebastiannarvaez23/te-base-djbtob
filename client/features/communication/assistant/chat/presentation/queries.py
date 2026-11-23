from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class AssistantConversationListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    limit = QueryParam(coerce=int, min_value=1, max_value=100)
