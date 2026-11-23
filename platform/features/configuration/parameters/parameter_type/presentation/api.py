from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.parameters.parameter_type.application.use_cases import (
    CreateParameterTypeUseCase,
    DeleteParameterTypeUseCase,
    GetAllParameterTypesUseCase,
    GetParameterTypeByIdUseCase,
    UpdateParameterTypeUseCase,
)
from platform.features.configuration.parameters.parameter_type.domain.schemas import (
    CreateParameterTypeSchema,
    UpdateParameterTypeSchema,
)
from platform.features.configuration.parameters.parameter_type.infrastructure.repositories import DjangoParameterTypeRepository
from platform.features.configuration.parameters.parameter_type.presentation.bodies import (
    CreateParameterTypeBody,
    UpdateParameterTypeBody,
)
from platform.features.configuration.parameters.parameter_type.presentation.queries import (
    ParameterTypeListQuery,
)


def _repo():
    return DjangoParameterTypeRepository()


def _catalog_response(query, items):
    dumped = [item.model_dump(mode='json') for item in items]
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


class ParameterTypeListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(ParameterTypeListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        items = GetAllParameterTypesUseCase(_repo()).execute(filters=query.filters)
        return _catalog_response(query, items)
    @validated_body(CreateParameterTypeBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateParameterTypeSchema(**body)
        result = CreateParameterTypeUseCase(_repo()).execute(schema)
        audit_log(
            request, 'ParameterType', result.id, 'CREATE',
            f'Parameter type created: {result.code}',
        )
        return wrap_response(
            result.model_dump(),
            status_code=201,
            message='The parameter type has been created successfully.',
        )


class ParameterTypeDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetParameterTypeByIdUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump())

    @validated_body(UpdateParameterTypeBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        schema = UpdateParameterTypeSchema(**body)
        result = UpdateParameterTypeUseCase(_repo()).execute(pk, schema)
        audit_log(
            request, 'ParameterType', pk, 'UPDATE',
            changes = body,
        )
        return wrap_response(result.model_dump())

    def delete(self, request, pk, *args, **kwargs):
        DeleteParameterTypeUseCase(_repo()).execute(pk)
        audit_log(request, 'ParameterType', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
