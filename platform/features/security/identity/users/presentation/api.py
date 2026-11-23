import uuid

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.security.identity.users.application.use_cases import (
    CreateAdminUserUseCase,
    GetAdminUserUseCase,
    ListAdminUsersPaginatedUseCase,
    ToggleAdminUserActiveUseCase,
    UpdateAdminUserUseCase,
)
from platform.features.security.identity.users.domain.schemas import CreateAdminUserSchema, UpdateAdminUserSchema
from platform.features.security.identity.users.infrastructure.repositories import DjangoAdminUserRepository
from platform.features.security.identity.users.presentation.queries import AdminUsersQuery
from platform.features.security.identity.users.presentation.bodies import (
    CreateAdminUserBody,
    UpdateAdminUserBody,
)


class AdminUserListCreateAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminUserRepository()

    @validated_query(AdminUsersQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListAdminUsersPaginatedUseCase(self._get_repository()).execute(query)
        return wrap_response({
            'items': [u.model_dump(mode='json') for u in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @validated_body(CreateAdminUserBody)
    def post(self, request, *, body: dict):
        schema = CreateAdminUserSchema(**body)
        user = CreateAdminUserUseCase(self._get_repository()).execute(schema)
        audit_log(request, 'AdminUser', user.id, 'CREATE', f'Admin user created: {schema.email}')
        return wrap_response(user.model_dump(mode='json'), status_code=201, message="The item has been created successfully.")


class AdminUserDetailAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminUserRepository()

    def get(self, request, user_id: uuid.UUID):
        user = GetAdminUserUseCase(self._get_repository()).execute(user_id)
        if user is None:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        return wrap_response(user.model_dump(mode='json'))

    @validated_body(UpdateAdminUserBody)
    def patch(self, request, user_id: uuid.UUID, *, body: dict):
        schema = UpdateAdminUserSchema(**body)
        user = UpdateAdminUserUseCase(self._get_repository()).execute(user_id, schema)
        if user is None:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'AdminUser', user_id, 'UPDATE', changes = body)
        return wrap_response(user.model_dump(mode='json'))


class AdminUserToggleActiveAPIView(APIView):
    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_repository(self):
        return DjangoAdminUserRepository()

    def post(self, request, user_id: uuid.UUID):
        user = ToggleAdminUserActiveUseCase(self._get_repository()).execute(user_id)
        if user is None:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'AdminUser', user_id, 'TOGGLE_ACTIVE', f'is_active={user.is_active}')
        return wrap_response(user.model_dump(mode='json'))
