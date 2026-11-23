from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from client.features.security.identity.users.application.use_cases import (
    CreateCompanyUserUseCase,
    ListCompanyUsersUseCase,
    ToggleCompanyUserActiveUseCase,
    UpdateCompanyUserUseCase,
)
from client.features.security.identity.users.domain.schemas import (
    CreateCompanyUserSchema,
    UpdateCompanyUserSchema,
)
from client.features.security.identity.users.infrastructure.repositories import DjangoCompanyUserRepository
from client.features.security.identity.users.application.check_availability import (
    CheckEmailAvailabilityUseCase,
    CheckUsernameAvailabilityUseCase,
)
from client.features.security.identity.users.presentation.bodies import (
    CheckCompanyEmailBody,
    CheckCompanyUsernameBody,
    CreateCompanyUserBody,
    UpdateCompanyUserBody,
)
from client.features.security.identity.users.presentation.queries import CompanyUsersQuery
from core.audit import audit_log
from core.access.decorators import track_usage
from core.access.enforcement import USERS_QUOTA_FEATURE
from core.decorators.response import wrap_response
from core.errors import AppErrorCode, NotFoundException, ValidationAppException
from core.permissions import HasSubscriptionAccess, IsCompanyMember
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body


class CheckCompanyUsernameAPIView(APIView):
    """Probe whether a username is still free before creating a company user."""

    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = 'security.users.create'
    subscription_check_quota = False

    @validated_body(CheckCompanyUsernameBody)
    def post(self, request, *, body: dict):
        available = CheckUsernameAvailabilityUseCase().execute(body['username'])
        return wrap_response({'available': available})


class CheckCompanyEmailAPIView(APIView):
    """Probe whether an email is still free before creating a company user."""

    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = 'security.users.create'
    subscription_check_quota = False

    @validated_body(CheckCompanyEmailBody)
    def post(self, request, *, body: dict):
        available = CheckEmailAvailabilityUseCase().execute(body['email'])
        return wrap_response({'available': available})


class CompanyUsersAPIView(APIView):
    """List and create users belonging to the authenticated user's company."""

    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = {
        'get': 'security.users.view',
        'post': USERS_QUOTA_FEATURE,
    }
    subscription_check_quota = False

    def _get_repository(self):
        return DjangoCompanyUserRepository()

    @validated_query(CompanyUsersQuery)
    def get(self, request, *, query: PaginatedQuery):
        use_case = ListCompanyUsersUseCase(self._get_repository())
        result = use_case.execute(
            company_id=request.user.company_id,
            filters=query.filters,
            page=query.page,
            page_size=query.page_size,
            offset=query.offset,
            limit=query.limit,
        )
        result['items'] = [item.model_dump() for item in result['items']]
        return wrap_response(result)

    @validated_body(CreateCompanyUserBody)
    @track_usage(USERS_QUOTA_FEATURE)
    def post(self, request, *, body: dict):

        schema = CreateCompanyUserSchema(**body, company_id=request.user.company_id)
        use_case = CreateCompanyUserUseCase(self._get_repository())
        user = use_case.execute(schema)
        audit_log(request, 'User', user.id, 'CREATE', f'Company user created: {body.get("username", "")}')
        return wrap_response(user.model_dump(), status_code=201, message="The item has been created successfully.")


class CompanyUserDetailAPIView(APIView):
    """Update a specific user belonging to the authenticated user's company."""

    permission_classes = [IsAuthenticated]

    @validated_body(UpdateCompanyUserBody)
    def patch(self, request, user_id, *, body: dict):

        schema = UpdateCompanyUserSchema(**body)
        use_case = UpdateCompanyUserUseCase(DjangoCompanyUserRepository())
        user = use_case.execute(user_id, request.user.company_id, schema)
        if not user:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'User', user_id, 'UPDATE', changes=body)
        return wrap_response(user.model_dump())


class CompanyUserToggleActiveAPIView(APIView):
    """Toggle the is_active flag for a company user."""

    permission_classes = [IsAuthenticated, IsCompanyMember, HasSubscriptionAccess]
    subscription_functionality = 'security.users.toggle-active'
    subscription_check_quota = False

    def post(self, request, user_id):
        if str(user_id) == str(request.user.id):
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='You cannot deactivate your own account.',
            )

        use_case = ToggleCompanyUserActiveUseCase(DjangoCompanyUserRepository())
        user = use_case.execute(user_id, request.user.company_id)
        if not user:
            raise NotFoundException(AppErrorCode.USER_NOT_FOUND)
        audit_log(request, 'User', user_id, 'TOGGLE_ACTIVE', f'is_active={user.is_active}')
        return wrap_response(user.model_dump())
