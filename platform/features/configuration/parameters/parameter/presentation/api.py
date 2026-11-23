from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication

from platform.features.configuration.parameters.parameter.application.use_cases import (
    CreateParameterUseCase,
    DeleteParameterUseCase,
    GetAllParametersUseCase,
    GetParameterByIdUseCase,
    UpdateParameterUseCase,
)
from platform.features.configuration.parameters.parameter.domain.schemas import (
    CreateParameterSchema,
    UpdateParameterSchema,
)
from platform.features.configuration.parameters.parameter.infrastructure.repositories import DjangoParameterRepository
from platform.features.configuration.parameters.parameter.presentation.bodies import (
    CreateParameterBody,
    UpdateParameterBody,
)
from platform.features.configuration.parameters.parameter.presentation.queries import ParameterListQuery


def _repo():
    return DjangoParameterRepository()


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


class ParameterListCreateView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(ParameterListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        items = GetAllParametersUseCase(_repo()).execute(filters=query.filters)
        return _catalog_response(query, items)

    @validated_body(CreateParameterBody)
    def post(self, request, *args, body: dict, **kwargs):
        schema = CreateParameterSchema(**body)
        result = CreateParameterUseCase(_repo()).execute(schema)
        audit_log(
            request, 'Parameter', result.id, 'CREATE',
            f'Parameter created: {result.code}',
        )
        return wrap_response(
            result.model_dump(),
            status_code=201,
            message='The parameter has been created successfully.',
        )


class ParameterDetailView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        result = GetParameterByIdUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump())

    @validated_body(UpdateParameterBody)
    def patch(self, request, pk, *args, body: dict, **kwargs):
        schema = UpdateParameterSchema(**body)
        result = UpdateParameterUseCase(_repo()).execute(pk, schema)
        audit_log(
            request, 'Parameter', pk, 'UPDATE',
            changes = body,
        )
        return wrap_response(result.model_dump())

    def delete(self, request, pk, *args, **kwargs):
        DeleteParameterUseCase(_repo()).execute(pk)
        audit_log(request, 'Parameter', pk, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)
