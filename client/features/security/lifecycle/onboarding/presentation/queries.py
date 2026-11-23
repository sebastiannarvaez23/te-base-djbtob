"""Query params for onboarding public policy reads."""

from core.query import QueryFilter, QueryParam


class OnboardingPublishedPolicyQuery(QueryFilter):
    """ISO country for the published policy version (optional if registration has it)."""

    ALLOW_UNPAGINATED = True

    country = QueryParam(coerce=str, max_length=2, pattern=r'^[A-Za-z]{2}$')
