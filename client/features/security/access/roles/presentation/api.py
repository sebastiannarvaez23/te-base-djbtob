from rest_framework import status
from core.auth.cookie_authentication import CookieTokenAuthentication as TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from client.features.security.access.roles.application.use_cases import (
    CreateGenericRoleUseCase,
    CreateRoleUseCase,
    DeleteRoleUseCase,
    ListFeaturesUseCase,
    ListGenericRolesUseCase,
    ListRolesUseCase,
    ToggleCompanyRolAccessUseCase,
    UpdateGenericRoleFeaturesUseCase,
    UpdateGenericRoleUseCase,
    UpdateRoleFeaturesUseCase,
    UpdateRoleUseCase,
)
from client.features.security.access.roles.domain.schemas import (
    CreateGenericRoleSchema, CreateRoleSchema, UpdateRoleFeaturesSchema, UpdateRoleSchema,
)
from client.features.security.access.roles.infrastructure.repositories import DjangoRoleRepository
from client.features.security.access.roles.presentation.bodies import (
    CreateRoleBody, UpdateRoleBody, UpdateRoleFeaturesBody, ToggleAccessBody,
)
from client.features.security.access.roles.presentation.queries import (
    FeaturesCatalogQuery,
    GenericRolesListQuery,
    RolesListQuery,
)
from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from core.query.core import PaginatedQuery, PaginatedResult
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication


def _list_payload(query: PaginatedQuery, result: PaginatedResult):
    items = [item.model_dump() for item in result.items]
    if query.unpaginated:
        return wrap_response(items)
    return wrap_response({
        'items': items,
        'total': result.total,
        'page': result.page,
        'page_size': result.page_size,
        'total_pages': result.total_pages,
    })


class RolesListCreateAPIView(APIView):
    """List all roles and create a new one."""

    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoRoleRepository()

    @validated_query(RolesListQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListRolesUseCase(self._get_repository()).execute(request.user.company_id, query)
        return _list_payload(query, result)

    @validated_body(CreateRoleBody)
    def post(self, request, *, body: dict):

        schema = CreateRoleSchema(**body, company_id=request.user.company_id)
        role = CreateRoleUseCase(self._get_repository()).execute(schema)
        audit_log(request, 'Rol', role.id, 'CREATE', f'Role created: {schema.name}')
        return wrap_response(role.model_dump(), status_code=201, message="The item has been created successfully.")


class RoleDetailAPIView(APIView):
    """Update and delete a specific role. Only company-owned roles are allowed."""

    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoRoleRepository()

    @validated_body(UpdateRoleBody)
    def patch(self, request, role_id, *, body: dict):

        schema = UpdateRoleSchema(**body)
        role = UpdateRoleUseCase(self._get_repository()).execute(role_id, request.user.company_id, schema)
        if not role:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(request, 'Rol', role_id, 'UPDATE', changes=body)
        return wrap_response(role.model_dump())

    def delete(self, request, role_id):
        deleted = DeleteRoleUseCase(self._get_repository()).execute(role_id, request.user.company_id)
        if not deleted:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(request, 'Rol', role_id, 'DELETE')
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeaturesListAPIView(APIView):
    """Catálogo de permisos de rol.

    Los complementos no se listan para la plataforma. Una empresa solo ve
    los que ya tiene contratados, para que su administrador los asigne.
    """

    authentication_classes = [AdminTokenAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoRoleRepository()

    @validated_query(FeaturesCatalogQuery)
    def get(self, request, *, query: PaginatedQuery):
        company_id = getattr(request.user, 'company_id', None)
        result = ListFeaturesUseCase(self._get_repository()).execute(query, company_id)
        return _list_payload(query, result)


class RoleFeaturesAPIView(APIView):
    """Asigna (reemplaza) las features de un rol especifico. Solo roles propios de la empresa."""

    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoRoleRepository()

    @validated_body(UpdateRoleFeaturesBody)
    def put(self, request, role_id, *, body: dict):

        schema = UpdateRoleFeaturesSchema(
            feature_keys=body.get('feature_keys', []),
            module_codes=body.get('module_codes', []),
        )
        role = UpdateRoleFeaturesUseCase(self._get_repository()).execute(role_id, request.user.company_id, schema)
        if not role:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(request, 'Rol', role_id, 'UPDATE_FEATURES',
                  changes={'feature_keys': schema.feature_keys, 'module_codes': schema.module_codes})
        return wrap_response(role.model_dump())


class RolCompanyAccessAPIView(APIView):
    """Activa o desactiva un rol generico para la empresa del usuario autenticado."""

    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoRoleRepository()

    @validated_body(ToggleAccessBody)
    def patch(self, request, role_id, *, body: dict):

        is_active = body['is_active']
        role = ToggleCompanyRolAccessUseCase(self._get_repository()).execute(role_id, request.user.company_id, is_active)
        if not role:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(request, 'Rol', role_id, 'TOGGLE_ACCESS', f'is_active={is_active}')
        return wrap_response(role.model_dump())


# ── Generic roles — platform admin endpoints ──────────────────────────────────


class GenericRolesListCreateAPIView(APIView):
    """List all generic roles and create new ones. Platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoRoleRepository()

    @validated_query(GenericRolesListQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListGenericRolesUseCase(self._get_repository()).execute(query)
        return _list_payload(query, result)

    @validated_body(CreateRoleBody)
    def post(self, request, *, body: dict):

        schema = CreateGenericRoleSchema(
            name=body['name'],
            description=body.get('description', ''),
        )
        role = CreateGenericRoleUseCase(self._get_repository()).execute(schema)
        audit_log(request, 'Rol', role.id, 'CREATE', f'Generic role created: {schema.name}')
        return wrap_response(role.model_dump(), status_code=201, message="The item has been created successfully.")


class GenericRoleDetailAPIView(APIView):
    """Update a specific generic role. Platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoRoleRepository()

    @validated_body(UpdateRoleBody)
    def patch(self, request, role_id, *, body: dict):

        schema = UpdateRoleSchema(**body)
        role = UpdateGenericRoleUseCase(self._get_repository()).execute(role_id, schema)
        if not role:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(request, 'Rol', role_id, 'UPDATE', changes=body)
        return wrap_response(role.model_dump())


class GenericRoleFeaturesAPIView(APIView):
    """Replace features/modules of a generic role. Platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoRoleRepository()

    @validated_body(UpdateRoleFeaturesBody)
    def put(self, request, role_id, *, body: dict):

        schema = UpdateRoleFeaturesSchema(
            feature_keys=body.get('feature_keys', []),
            module_codes=body.get('module_codes', []),
        )
        role = UpdateGenericRoleFeaturesUseCase(self._get_repository()).execute(role_id, schema)
        if not role:
            raise NotFoundException(AppErrorCode.ROLE_NOT_FOUND)
        audit_log(request, 'Rol', role_id, 'UPDATE_FEATURES',
                  changes={'feature_keys': schema.feature_keys, 'module_codes': schema.module_codes})
        return wrap_response(role.model_dump())
