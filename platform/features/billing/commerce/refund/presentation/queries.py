from core.query import PATTERN_CODE, PATTERN_TEXT, QueryFilter, QueryParam


class AdminRefundQuery(QueryFilter):
    ticket_number = QueryParam(coerce=str, max_length=24, pattern=PATTERN_CODE)
    company = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    status = QueryParam(
        coerce=str,
        choices=['pending', 'accepted', 'processing', 'completed', 'failed', 'rejected'],
    )
