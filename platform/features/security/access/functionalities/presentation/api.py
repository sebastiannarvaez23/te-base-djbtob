import uuid

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
from platform.features.security.access.functionalities.application.use_cases import (
    AssignFunctionalityToModuleUseCase,
    CreateFunctionalityUseCase,
    DeleteFunctionalityUseCase,
    GetFunctionalityUseCase,
    ListFunctionalitiesPaginatedUseCase,
    ToggleFunctionalityUseCase,
    UpdateFunctionalityUseCase,
)
from platform.features.security.access.functionalities.domain.schemas import (
    AssignFunctionalitySchema,
    CreateFunctionalitySchema,
    UpdateFunctionalitySchema,
)
from platform.features.security.access.functionalities.infrastructure.repositories import DjangoFunctionalityRepository
from platform.features.security.access.functionalities.presentation.bodies import (
    AssignFunctionalityBody,
    CreateFunctionalityBody,
    UpdateFunctionalityBody,
)
from platform.features.security.access.functionalities.presentation.queries import FunctionalityQuery


class FunctionalityListCreateAPIView(APIView):
    """Paginated list + create — platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(FunctionalityQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListFunctionalitiesPaginatedUseCase(DjangoFunctionalityRepository()).execute(query)
        return wrap_response({
            'items': [f.model_dump() for f in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @validated_body(CreateFunctionalityBody)
    def post(self, request, *, body: dict):

        schema = CreateFunctionalitySchema(**body)
        func = CreateFunctionalityUseCase(DjangoFunctionalityRepository()).execute(schema)
        audit_log(request, 'Functionality', func.id, 'CREATE', f'Functionality created: {schema.key}')
        return wrap_response(func.model_dump(), status_code=201, message='Functionality created successfully.')


class FunctionalityDetailAPIView(APIView):
    """Retrieve, update or delete a single functionality."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, functionality_id: uuid.UUID):
        func = GetFunctionalityUseCase(DjangoFunctionalityRepository()).execute(functionality_id)
        if func is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Functionality not found.')
        return wrap_response(func.model_dump())

    @validated_body(UpdateFunctionalityBody)
    def patch(self, request, functionality_id: uuid.UUID, *, body: dict):

        schema = UpdateFunctionalitySchema(**body)
        func = UpdateFunctionalityUseCase(DjangoFunctionalityRepository()).execute(functionality_id, schema)
        if func is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Functionality not found.')
        audit_log(request, 'Functionality', functionality_id, 'UPDATE', changes=body)
        return wrap_response(func.model_dump())

    def delete(self, request, functionality_id: uuid.UUID):
        deleted = DeleteFunctionalityUseCase(DjangoFunctionalityRepository()).execute(functionality_id)
        if not deleted:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Functionality not found.')
        audit_log(request, 'Functionality', functionality_id, 'DELETE', f'Functionality deleted: {functionality_id}')
        return Response(status=status.HTTP_204_NO_CONTENT)


class FunctionalityToggleAPIView(APIView):
    """Toggle the is_active state of a functionality."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, functionality_id: uuid.UUID):
        func = ToggleFunctionalityUseCase(DjangoFunctionalityRepository()).execute(functionality_id)
        if func is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Functionality not found.')
        audit_log(request, 'Functionality', functionality_id, 'TOGGLE', f'is_active={func.is_active}')
        return wrap_response(func.model_dump())


class FunctionalityAssignAPIView(APIView):
    """Assign a functionality to a different module."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(AssignFunctionalityBody)
    def post(self, request, functionality_id: uuid.UUID, *, body: dict):

        schema = AssignFunctionalitySchema(**body)
        func = AssignFunctionalityToModuleUseCase(DjangoFunctionalityRepository()).execute(functionality_id, schema)
        if func is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND, override_detail='Functionality not found.')
        audit_log(request, 'Functionality', functionality_id, 'ASSIGN', f'Assigned to module={schema.module}')
        return wrap_response(func.model_dump(), message='Functionality assigned successfully.')
