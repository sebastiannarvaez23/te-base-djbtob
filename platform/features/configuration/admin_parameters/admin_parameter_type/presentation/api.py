from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.admin_parameters.admin_parameter_type.application.use_cases import (
    CreateAdminParameterTypeUseCase,
    DeleteAdminParameterTypeUseCase,
    GetAdminParameterTypeByIdUseCase,
    GetAllAdminParameterTypesUseCase,
    UpdateAdminParameterTypeUseCase,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.domain.schemas import (
    CreateAdminParameterTypeSchema,
    UpdateAdminParameterTypeSchema,
)
from platform.features.configuration.admin_parameters.admin_parameter.infrastructure.repositories import (
    DjangoAdminParameterRepository,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.infrastructure.repositories import (
    DjangoAdminParameterTypeRepository,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.presentation.bodies import (
    CreateAdminParameterTypeBody,
    UpdateAdminParameterTypeBody,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.presentation.queries import (
    AdminParameterTypeListQuery,
)


def _repo():
    return DjangoAdminParameterTypeRepository()


def _param_repo():
    return DjangoAdminParameterRepository()


class AdminParameterTypeListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(AdminParameterTypeListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        items = GetAllAdminParameterTypesUseCase(_repo()).execute(filters=query.filters)
        return wrap_response([item.model_dump(mode='json') for item in items])

    @validated_body(CreateAdminParameterTypeBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateAdminParameterTypeSchema(**body)
        result = CreateAdminParameterTypeUseCase(_repo()).execute(schema)
        audit_log(
            request, 'AdminParameterType', result.id, 'CREATE',
            f'Admin parameter type created: {result.code}',
        )
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message='The admin parameter type has been created successfully.',
        )


class AdminParameterTypeDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetAdminParameterTypeByIdUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateAdminParameterTypeBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        schema = UpdateAdminParameterTypeSchema(**body)
        result = UpdateAdminParameterTypeUseCase(_repo()).execute(pk, schema)
        audit_log(
            request, 'AdminParameterType', pk, 'UPDATE',
            changes=body,
        )
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, *args, **kwargs):
        DeleteAdminParameterTypeUseCase(_repo(), _param_repo()).execute(pk)
        audit_log(request, 'AdminParameterType', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
