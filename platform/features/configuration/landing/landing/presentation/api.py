from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.landing.landing.application.use_cases import (
    ListLandingSectionsUseCase,
    ToggleLandingSectionUseCase,
)
from platform.features.configuration.landing.landing.infrastructure.repositories import (
    DjangoLandingSectionRepository,
)
from platform.features.configuration.landing.landing.presentation.bodies import (
    ToggleLandingSectionBody,
)
from platform.features.configuration.landing.landing.presentation.queries import (
    LandingSectionListQuery,
)


def _repo():
    return DjangoLandingSectionRepository()


def _catalog_response(query, items):
    dumped = [r.model_dump(mode='json') for r in items]
    if query.unpaginated:
        return wrap_response(dumped)
    total = len(dumped)
    page_items = dumped[query.offset: query.offset + query.page_size]
    return wrap_response({
        'items': page_items,
        'total': total,
        'page': query.page,
        'page_size': query.page_size,
        'total_pages': (total + query.page_size - 1) // query.page_size if query.page_size else 1,
    })


class LandingSectionListView(APIView):
    """``GET /api/v1/platform/landing-sections/`` — admin list."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(LandingSectionListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        rows = ListLandingSectionsUseCase(_repo()).execute(filters=query.filters)
        return _catalog_response(query, rows)


class LandingSectionToggleView(APIView):
    """``PATCH /api/v1/platform/landing-sections/<key>/`` — set visibility."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(ToggleLandingSectionBody)
    def patch(self, request, key, *args, body: dict, **kwargs):
        result = ToggleLandingSectionUseCase(_repo()).execute(
            key, body['is_visible'],
        )
        audit_log(
            request, 'LandingSection', result.id or key, 'UPDATE',
            changes={'key': key, 'is_visible': result.is_visible},
        )
        return wrap_response(result.model_dump(mode='json'))
