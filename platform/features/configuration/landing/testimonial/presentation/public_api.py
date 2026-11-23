"""Published testimonials for base-landing-web (anonymous)."""

from rest_framework.views import APIView

from core.query import PaginatedQuery, validated_query

from platform.features.configuration.landing.testimonial.application.use_cases import (
    ListPublicTestimonialsUseCase,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    TestimonialListFilters,
)
from platform.features.configuration.landing.testimonial.infrastructure.repositories import (
    DjangoTestimonialRepository,
)
from platform.features.configuration.landing.testimonial.presentation.catalog import catalog_response
from platform.features.configuration.landing.testimonial.presentation.queries import (
    PublicTestimonialListQuery,
)


class PublicTestimonialsAPIView(APIView):
    """``GET /api/v1/landing/testimonials/`` — published quotes."""

    authentication_classes = []
    permission_classes = []

    @validated_query(PublicTestimonialListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        filters = TestimonialListFilters.from_query(query.filters)
        unpaged = query.unpaginated
        page = ListPublicTestimonialsUseCase(
            DjangoTestimonialRepository(),
        ).execute(
            filters,
            offset=None if unpaged else query.offset,
            limit=None if unpaged else query.limit,
        )
        return catalog_response(query, page.items, total=page.total)
