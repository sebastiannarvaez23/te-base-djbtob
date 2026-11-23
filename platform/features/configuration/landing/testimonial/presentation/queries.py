from core.query import PATTERN_TEXT, QueryFilter, QueryParam


class TestimonialListQuery(QueryFilter):
    __test__ = False
    ALLOW_UNPAGINATED = True

    q = QueryParam(coerce=str, max_length=200, pattern=PATTERN_TEXT)
    author_id = QueryParam(coerce=str, is_uuid=True)
    score = QueryParam(coerce=int, min_value=1, max_value=5)
    is_published = QueryParam(coerce=bool)
    locale = QueryParam(coerce=str, choices=['es', 'en'])
    signed = QueryParam(coerce=bool)


class PublicTestimonialListQuery(QueryFilter):
    ALLOW_UNPAGINATED = True

    locale = QueryParam(coerce=str, choices=['es', 'en'])
