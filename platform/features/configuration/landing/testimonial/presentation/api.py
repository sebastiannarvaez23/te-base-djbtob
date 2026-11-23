from uuid import UUID

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.landing.testimonial.application.use_cases import (
    CreateTestimonialUseCase,
    GetTestimonialUseCase,
    ListTestimonialsUseCase,
    UpdateTestimonialUseCase,
)
from platform.features.configuration.landing.testimonial.domain.schemas import (
    CreateTestimonialSchema,
    TestimonialListFilters,
    UpdateTestimonialSchema,
)
from platform.features.configuration.landing.testimonial.infrastructure.repositories import (
    DjangoTestimonialRepository,
)
from platform.features.configuration.landing.testimonial.presentation.bodies import (
    CreateTestimonialBody,
    UpdateTestimonialBody,
)
from platform.features.configuration.landing.testimonial.presentation.catalog import catalog_response
from platform.features.configuration.landing.testimonial.presentation.queries import (
    TestimonialListQuery,
)


def _repo():
    return DjangoTestimonialRepository()


def _as_uuid(pk) -> UUID:
    if isinstance(pk, UUID):
        return pk
    return UUID(str(pk))


class TestimonialListCreateView(APIView):
    """``GET/POST /api/v1/platform/testimonials/`` — admin catalog."""

    __test__ = False

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(TestimonialListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        filters = TestimonialListFilters.from_query(query.filters)
        unpaged = query.unpaginated
        page = ListTestimonialsUseCase(_repo()).execute(
            filters,
            offset=None if unpaged else query.offset,
            limit=None if unpaged else query.limit,
        )
        return catalog_response(query, page.items, total=page.total)

    @validated_body(CreateTestimonialBody)
    def post(self, request, *args, body: dict, **kwargs):
        result = CreateTestimonialUseCase(_repo()).execute(
            CreateTestimonialSchema(**body),
        )
        audit_log(
            request, 'Testimonial', result.id, 'CREATE',
            f'Testimonial created for author {result.author_id}',
        )
        return wrap_response(result.model_dump(mode='json'), status_code=201)


class TestimonialDetailView(APIView):
    """``GET/PATCH /api/v1/platform/testimonials/<uuid>/``."""

    __test__ = False

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetTestimonialUseCase(_repo()).execute(_as_uuid(pk))
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateTestimonialBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        result = UpdateTestimonialUseCase(_repo()).execute(
            _as_uuid(pk), UpdateTestimonialSchema(**body),
        )
        audit_log(request, 'Testimonial', pk, 'UPDATE', changes=body)
        return wrap_response(result.model_dump(mode='json'))
