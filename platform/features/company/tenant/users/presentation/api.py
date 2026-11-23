import uuid

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException
from core.query import PaginatedQuery, validated_query
from platform.core.authentication import AdminTokenAuthentication
from platform.features.company.tenant.users.application.use_cases import (
    ListTenantUsersPaginatedUseCase,
    ToggleTenantUserActiveUseCase,
)
from platform.features.company.tenant.users.infrastructure.repositories import DjangoTenantUserRepository
from platform.features.company.tenant.users.presentation.queries import TenantUsersQuery


class TenantUserListAPIView(APIView):
    """Paginated list of users across all companies — platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(TenantUsersQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListTenantUsersPaginatedUseCase(DjangoTenantUserRepository()).execute(query)
        return wrap_response({
            'items': [item.model_dump() for item in result.items],
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })


class TenantUserToggleActiveAPIView(APIView):
    """Toggle the is_active flag for a tenant user — platform admin only."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id: uuid.UUID):
        user = ToggleTenantUserActiveUseCase(DjangoTenantUserRepository()).execute(user_id)
        if not user:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'TenantUser', user_id, 'TOGGLE_ACTIVE', f'is_active={user.is_active}')
        return wrap_response(user.model_dump())
