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
from platform.features.security.access.roles.application.use_cases import (
    CreateAdminRoleUseCase,
    DeleteAdminRoleUseCase,
    ListAdminFeaturesUseCase,
    ListAdminModulesUseCase,
    ListAdminRolesUseCase,
    UpdateAdminRoleFeaturesUseCase,
    UpdateAdminRoleUseCase,
)
from platform.features.security.access.roles.domain.schemas import (
    CreateAdminRoleSchema,
    UpdateAdminRoleFeaturesSchema,
    UpdateAdminRoleSchema,
)
from platform.features.security.access.roles.infrastructure.repositories import DjangoAdminRoleRepository
from platform.features.security.access.roles.presentation.bodies import (
    CreateAdminRoleBody,
    UpdateAdminRoleBody,
    UpdateAdminRoleFeaturesBody,
)
from platform.features.security.access.roles.presentation.queries import (
    AdminFeaturesCatalogQuery,
    AdminModulesCatalogQuery,
    AdminRoleListQuery,
)


def _catalog_response(query, items):
    dumped = [i.model_dump(mode='json') for i in items]
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


class AdminRoleListCreateAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminRoleRepository()

    @validated_query(AdminRoleListQuery)
    def get(self, request, *, query: PaginatedQuery):
        roles = ListAdminRolesUseCase(self._get_repository()).execute(filters=query.filters)
        return _catalog_response(query, roles)

    @validated_body(CreateAdminRoleBody)
    def post(self, request, *, body: dict):
        schema = CreateAdminRoleSchema(**body)
        role = CreateAdminRoleUseCase(self._get_repository()).execute(schema)
        audit_log(request, 'AdminRole', role.id, 'CREATE', f'Admin role created: {schema.name}')
        return wrap_response(role.model_dump(mode='json'), status_code=201, message="The item has been created successfully.")


class AdminRoleDetailAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminRoleRepository()

    @validated_body(UpdateAdminRoleBody)
    def patch(self, request, role_id: uuid.UUID, *, body: dict):
        schema = UpdateAdminRoleSchema(**body)
        role = UpdateAdminRoleUseCase(self._get_repository()).execute(role_id, schema)
        if role is None:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(request, 'AdminRole', role_id, 'UPDATE', changes = body)
        return wrap_response(role.model_dump(mode='json'))

    def delete(self, request, role_id: uuid.UUID):
        deleted = DeleteAdminRoleUseCase(self._get_repository()).execute(role_id)
        if not deleted:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(request, 'AdminRole', role_id, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminModulesCatalogAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminRoleRepository()

    @validated_query(AdminModulesCatalogQuery)
    def get(self, request, *, query: PaginatedQuery):
        modules = ListAdminModulesUseCase(self._get_repository()).execute(filters=query.filters)
        return _catalog_response(query, modules)


class AdminFeaturesCatalogAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminRoleRepository()

    @validated_query(AdminFeaturesCatalogQuery)
    def get(self, request, *, query: PaginatedQuery):
        features = ListAdminFeaturesUseCase(self._get_repository()).execute(filters=query.filters)
        return _catalog_response(query, features)


class AdminRoleFeaturesAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminRoleRepository()

    @validated_body(UpdateAdminRoleFeaturesBody)
    def put(self, request, role_id: uuid.UUID, *, body: dict):
        schema = UpdateAdminRoleFeaturesSchema(**body)
        role = UpdateAdminRoleFeaturesUseCase(self._get_repository()).execute(role_id, schema)
        if role is None:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(
            request, 'AdminRole', role_id, 'UPDATE_FEATURES',
            changes={
                'feature_keys': schema.feature_keys,
                'module_codes': schema.module_codes,
            },
        )
        return wrap_response(role.model_dump(mode='json'))
