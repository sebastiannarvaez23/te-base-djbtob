from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from client.features.security.access.features.application.use_cases import (
    CreateFeatureUseCase,
    DeleteFeatureUseCase,
    ListFeaturesUseCase,
    UpdateFeatureUseCase,
)
from client.features.security.access.features.domain.schemas import CreateFeatureSchema, UpdateFeatureSchema
from client.features.security.access.features.infrastructure.repositories import DjangoFeatureRepository
from client.features.security.access.features.presentation.bodies import CreateFeatureBody, UpdateFeatureBody
from client.features.security.access.features.presentation.queries import FeatureListQuery
from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication


class FeatureListCreateAPIView(APIView):
    """List all features (optionally filtered by module) and create a new one."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(FeatureListQuery)
    def get(self, request, *, query: PaginatedQuery):
        module = query.filters.get('module')
        features = ListFeaturesUseCase(DjangoFeatureRepository()).execute(module=module)
        return wrap_response([f.model_dump() for f in features])

    @validated_body(CreateFeatureBody)
    def post(self, request, *, body: dict):

        schema = CreateFeatureSchema(**body)
        feature = CreateFeatureUseCase(DjangoFeatureRepository()).execute(schema)
        audit_log(request, 'Feature', feature.id, 'CREATE', f'Feature created: {schema.key}')
        return wrap_response(feature.model_dump(), status_code=201, message='Feature created successfully.')


class FeatureDetailAPIView(APIView):
    """Update or delete a specific feature."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, feature_id):
        deleted = DeleteFeatureUseCase(DjangoFeatureRepository()).execute(feature_id)
        if not deleted:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Feature not found.')
        audit_log(request, 'Feature', feature_id, 'DELETE', f'Feature deleted: {feature_id}')
        return Response(status=status.HTTP_204_NO_CONTENT)

    @validated_body(UpdateFeatureBody)
    def patch(self, request, feature_id, *, body: dict):

        schema = UpdateFeatureSchema(**body)
        feature = UpdateFeatureUseCase(DjangoFeatureRepository()).execute(feature_id, schema)
        if not feature:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Feature not found.')
        audit_log(request, 'Feature', feature_id, 'UPDATE', changes=body)
        return wrap_response(feature.model_dump())
