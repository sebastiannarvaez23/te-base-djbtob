from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.release.feature_flag.feature_flag.application.use_cases import (
    CreateFeatureFlagUseCase,
    DeleteFeatureFlagUseCase,
    GetAllFeatureFlagsUseCase,
    GetFeatureFlagByIdUseCase,
    SetFeatureFlagStatusUseCase,
    ToggleFeatureFlagEnabledUseCase,
    UpdateFeatureFlagUseCase,
)
from platform.features.release.feature_flag.feature_flag.domain.schemas import (
    CreateFeatureFlagSchema,
    UpdateFeatureFlagSchema,
)
from platform.features.release.feature_flag.feature_flag.infrastructure.repositories import (
    DjangoFeatureFlagRepository,
)
from platform.features.release.feature_flag.feature_flag.presentation.bodies import (
    CreateFeatureFlagBody,
    SetFeatureFlagStatusBody,
    ToggleFeatureFlagBody,
    UpdateFeatureFlagBody,
)
from platform.features.release.feature_flag.feature_flag.presentation.queries import FeatureFlagListQuery


def _repo():
    return DjangoFeatureFlagRepository()


def _dump(schema) -> dict:
    return schema.model_dump(mode='json')


def _catalog_response(query, items):
    dumped = [_dump(item) for item in items]
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


class FeatureFlagListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(FeatureFlagListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        result = GetAllFeatureFlagsUseCase(_repo()).execute(filters=query.filters)
        return _catalog_response(query, result)

    @validated_body(CreateFeatureFlagBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateFeatureFlagSchema(**body)
        result = CreateFeatureFlagUseCase(_repo()).execute(schema)
        audit_log(
            request, 'FeatureFlag', result.id, 'CREATE',
            f'Feature flag created: {result.key}',
        )
        return wrap_response(
            _dump(result),
            status_code=201,
            message='The feature flag has been created successfully.',
        )


class FeatureFlagDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetFeatureFlagByIdUseCase(_repo()).execute(pk)
        return wrap_response(_dump(result))

    @validated_body(UpdateFeatureFlagBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        schema = UpdateFeatureFlagSchema(**body)
        result = UpdateFeatureFlagUseCase(_repo()).execute(pk, schema)
        audit_log(
            request, 'FeatureFlag', pk, 'UPDATE',
            changes = body,
        )
        return wrap_response(_dump(result))

    def delete(self, request, pk, *args, **kwargs):
        DeleteFeatureFlagUseCase(_repo()).execute(pk)
        audit_log(request, 'FeatureFlag', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeatureFlagToggleView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(ToggleFeatureFlagBody)
    def post(self, request, pk, *args, body: dict, **kwargs):
        result = ToggleFeatureFlagEnabledUseCase(_repo()).execute(
            pk, body['enabled'],
        )
        audit_log(
            request, 'FeatureFlag', pk, 'TOGGLE',
            f'enabled={result.enabled}',
        )
        return wrap_response(_dump(result))


class FeatureFlagStatusView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(SetFeatureFlagStatusBody)
    def post(self, request, pk, *args, body: dict, **kwargs):
        result = SetFeatureFlagStatusUseCase(_repo()).execute(
            pk, body['status'],
        )
        audit_log(
            request, 'FeatureFlag', pk, 'UPDATE_STATUS',
            f'status={result.status}',
        )
        return wrap_response(_dump(result))
