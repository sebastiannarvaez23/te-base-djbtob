import uuid

from rest_framework import status
from core.auth.cookie_authentication import CookieTokenAuthentication as TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, ConflictException, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.security.catalog_order import parse_uuid_ids
from platform.features.security.access.modules.application.use_cases import (
    CreateModuleUseCase,
    DeleteModuleUseCase,
    GetModuleUseCase,
    ListModulesPaginatedUseCase,
    ListModulesUseCase,
    ReorderModulesUseCase,
    ToggleModuleUseCase,
    UpdateModuleUseCase,
)
from platform.features.security.access.modules.domain.schemas import CreateModuleSchema, UpdateModuleSchema
from platform.features.security.access.modules.infrastructure.repositories import DjangoModuleRepository
from platform.features.security.access.modules.presentation.bodies import (
    CreateModuleBody,
    ReorderModuleBody,
    UpdateModuleBody,
)
from platform.features.security.access.modules.presentation.queries import ModuleCatalogQuery, ModuleQuery


class ModuleListAPIView(APIView):
    """List active modules — accessible by company users or platform admins."""

    authentication_classes = [AdminTokenAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(ModuleCatalogQuery)
    def get(self, request, *, query: PaginatedQuery):
        repository = DjangoModuleRepository()
        if query.unpaginated:
            items = ListModulesUseCase(repository).execute(query.filters)
            return wrap_response([item.model_dump(mode='json') for item in items])
        result = ListModulesPaginatedUseCase(repository).execute(query)
        return wrap_response({
            'items': [item.model_dump(mode='json') for item in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })


class ModuleAdminListAPIView(APIView):
    """Paginated module list for platform admin management."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(ModuleQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListModulesPaginatedUseCase(DjangoModuleRepository()).execute(query)
        return wrap_response({
            'items': [m.model_dump() for m in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })


class ModuleCreateAPIView(APIView):
    """Create a new module — platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(CreateModuleBody)
    def post(self, request, *, body: dict):

        schema = CreateModuleSchema(**body)
        module = CreateModuleUseCase(DjangoModuleRepository()).execute(schema)
        audit_log(request, 'Module', module.id, 'CREATE', f'Module created: {schema.code}')
        return wrap_response(module.model_dump(), status_code=201, message='Module created successfully.')


class ModuleReorderAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(ReorderModuleBody)
    def patch(self, request, *, body: dict):
        ids = parse_uuid_ids(body['ids'])
        count = ReorderModulesUseCase(DjangoModuleRepository()).execute(ids)
        audit_log(request, 'Module', '', 'REORDER', f'count={count}')
        return wrap_response({'count': count})


class ModuleDetailAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, module_id: uuid.UUID):
        module = GetModuleUseCase(DjangoModuleRepository()).execute(module_id)
        if module is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND)
        return wrap_response(module.model_dump())

    @validated_body(UpdateModuleBody)
    def patch(self, request, module_id: uuid.UUID, *, body: dict):

        schema = UpdateModuleSchema(**body)
        module = UpdateModuleUseCase(DjangoModuleRepository()).execute(module_id, schema)
        if module is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND)
        audit_log(request, 'Module', module_id, 'UPDATE', changes=body)
        return wrap_response(module.model_dump())

    def delete(self, request, module_id: uuid.UUID):
        from django.db import IntegrityError
        from django.db.models.deletion import ProtectedError
        try:
            deleted = DeleteModuleUseCase(DjangoModuleRepository()).execute(module_id)
        except (ProtectedError, IntegrityError) as exc:
            raise ConflictException(AppErrorCode.MODULE_HAS_DEPENDENCIES) from exc
        if not deleted:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND)
        audit_log(request, 'Module', module_id, 'DELETE', f'Module deleted: {module_id}')
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModuleToggleAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, module_id: uuid.UUID):
        module = ToggleModuleUseCase(DjangoModuleRepository()).execute(module_id)
        if module is None:
            raise NotFoundException(AppErrorCode.MODULE_NOT_FOUND)
        audit_log(request, 'Module', module_id, 'TOGGLE', f'is_active={module.is_active}')
        return wrap_response(module.model_dump())
