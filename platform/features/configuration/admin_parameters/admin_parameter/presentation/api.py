from pydantic import ValidationError as PydanticValidationError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, ValidationAppException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.admin_parameters.admin_parameter.application.use_cases import (
    CreateAdminParameterUseCase,
    DeleteAdminParameterUseCase,
    GetAdminParameterByIdUseCase,
    GetAllAdminParametersUseCase,
    UpdateAdminParameterUseCase,
)
from platform.features.configuration.admin_parameters.admin_parameter.domain.schemas import (
    CreateAdminParameterSchema,
    UpdateAdminParameterSchema,
)
from platform.features.configuration.admin_parameters.admin_parameter.infrastructure.repositories import (
    DjangoAdminParameterRepository,
)
from platform.features.configuration.admin_parameters.admin_parameter.presentation.bodies import (
    CreateAdminParameterBody,
    UpdateAdminParameterBody,
)
from platform.features.configuration.admin_parameters.admin_parameter.presentation.queries import (
    AdminParameterListQuery,
)
from platform.features.configuration.admin_parameters.admin_parameter_type.infrastructure.repositories import (
    DjangoAdminParameterTypeRepository,
)


def _repo():
    return DjangoAdminParameterRepository()


def _type_repo():
    return DjangoAdminParameterTypeRepository()


def _schema_or_validation(schema_cls, body: dict):
    try:
        return schema_cls(**body)
    except PydanticValidationError as exc:
        detail = '; '.join(
            f"{'.'.join(str(p) for p in err.get('loc', ()))}: {err.get('msg')}"
            for err in exc.errors()
        ) or 'Invalid admin parameter payload.'
        raise ValidationAppException(
            AppErrorCode.APARAM_INVALID_VALUE,
            override_detail=detail,
        ) from exc


class AdminParameterListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(AdminParameterListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        items = GetAllAdminParametersUseCase(_repo()).execute(filters=query.filters)
        return wrap_response([item.model_dump(mode='json') for item in items])

    @validated_body(CreateAdminParameterBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = _schema_or_validation(CreateAdminParameterSchema, body)
        result = CreateAdminParameterUseCase(_repo(), _type_repo()).execute(schema)
        audit_log(
            request, 'AdminParameter', result.id, 'CREATE',
            f'Admin parameter created: {result.code}',
        )
        return wrap_response(
            result.model_dump(mode='json'),
            status_code=201,
            message='The admin parameter has been created successfully.',
        )


class AdminParameterDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetAdminParameterByIdUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateAdminParameterBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        schema = _schema_or_validation(UpdateAdminParameterSchema, body)
        result = UpdateAdminParameterUseCase(_repo(), _type_repo()).execute(pk, schema)
        audit_log(
            request, 'AdminParameter', pk, 'UPDATE',
            changes=body,
        )
        return wrap_response(result.model_dump(mode='json'))

    def delete(self, request, pk, *args, **kwargs):
        DeleteAdminParameterUseCase(_repo()).execute(pk)
        audit_log(request, 'AdminParameter', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
