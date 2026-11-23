"""HTTP API for Integration Application OAuth.

Validation flow (platform standard):
  RequestBody / QueryFilter (types, lengths, choices, English errors[])
  → Pydantic domain schema (strict types)
  → use case (business rules, status machine)
"""
from __future__ import annotations

import uuid

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from client.features.integrations.oauth.client.application.use_cases import (
    CreateIntegrationApplicationUseCase,
    DeleteIntegrationApplicationUseCase,
    DisableIntegrationApplicationUseCase,
    EnableIntegrationApplicationUseCase,
    GetIntegrationApplicationUseCase,
    IssueClientCredentialsTokenUseCase,
    ListGrantableIntegrationScopesUseCase,
    ListIntegrationApplicationsUseCase,
    RevokeIntegrationApplicationUseCase,
    RotateIntegrationApplicationSecretUseCase,
    UpdateIntegrationApplicationUseCase,
)
from client.features.integrations.oauth.client.domain.schemas import (
    CreatedApplicationCredentialsSchema,
    parse_create_integration_application_schema,
    parse_issue_token_input_schema,
    parse_update_integration_application_schema,
)
from client.features.integrations.oauth.client.infrastructure.credentials import SecureCredentialFactory
from client.features.integrations.oauth.client.infrastructure.repositories import (
    DjangoIntegrationApplicationRepository,
)
from client.features.integrations.oauth.client.infrastructure.scope_catalog import AccessControlScopeCatalog
from client.features.integrations.oauth.client.presentation.bodies import (
    CreateIntegrationApplicationBody,
    IssueTokenBody,
    UpdateIntegrationApplicationBody,
)
from client.features.integrations.oauth.client.presentation.queries import IntegrationApplicationListQuery
from core.audit import audit_log, security_log
from core.decorators.response import wrap_response
from core.errors import AuthException
from core.permissions import IsCompanyMember, company_for_request
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body

_ENTITY = 'IntegrationApplication'


def _repo() -> DjangoIntegrationApplicationRepository:
    return DjangoIntegrationApplicationRepository()


def _credentials() -> SecureCredentialFactory:
    return SecureCredentialFactory()


def _actor_scopes(request) -> AccessControlScopeCatalog:
    return AccessControlScopeCatalog(company_for_request(request), request.user)


def _tenant_scopes(request) -> AccessControlScopeCatalog:
    return AccessControlScopeCatalog(getattr(request, 'tenant', None))


def _actor_id(request) -> uuid.UUID | None:
    raw = getattr(request.user, 'id', None)
    try:
        return uuid.UUID(str(raw)) if raw not in (None, '') else None
    except ValueError:
        return None


def _credentials_payload(result: CreatedApplicationCredentialsSchema) -> dict:
    return {
        'application': result.application.model_dump(mode='json'),
        'client_secret': result.client_secret,
    }


class OAuthTokenAPIView(APIView):
    """OAuth 2.0 token endpoint (client_credentials)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @validated_body(IssueTokenBody)
    def post(self, request, *, body: dict):
        schema = parse_issue_token_input_schema(**body)
        try:
            result = IssueClientCredentialsTokenUseCase(
                _repo(), _credentials(), _tenant_scopes(request),
            ).execute(schema)
        except AuthException as exc:
            security_log(
                request,
                event_type='integration_oauth_token_denied',
                detail=f'client_id={schema.client_id} code={exc.code.value}',
            )
            raise
        security_log(
            request,
            event_type='integration_oauth_token_issued',
            detail=f'client_id={schema.client_id}',
        )
        return wrap_response(result.model_dump(mode='json'), message='Access token issued.')


class IntegrationScopeListView(APIView):
    """API permissions the current user may grant to an application (plan ∩ role)."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request):
        scopes = ListGrantableIntegrationScopesUseCase(_actor_scopes(request)).execute()
        return wrap_response([scope.model_dump(mode='json') for scope in scopes])


class IntegrationApplicationListCreateView(APIView):
    """IT admin: list / create Integration Applications."""

    permission_classes = [IsAuthenticated, IsCompanyMember]

    @validated_query(IntegrationApplicationListQuery)
    def get(self, request, *, query: PaginatedQuery):
        result = ListIntegrationApplicationsUseCase(_repo()).execute(query)
        items = [item.model_dump(mode='json') for item in result.items]
        if query.unpaginated:
            return wrap_response(items)
        return wrap_response({
            'items': items,
            'total': result.total,
            'page': result.page,
            'page_size': result.page_size,
            'total_pages': result.total_pages,
        })

    @validated_body(CreateIntegrationApplicationBody)
    def post(self, request, *, body: dict):
        schema = parse_create_integration_application_schema(**body)
        result = CreateIntegrationApplicationUseCase(
            _repo(), _credentials(), _actor_scopes(request),
        ).execute(
            schema,
            created_by=_actor_id(request),
        )
        app = result.application
        audit_log(
            request, _ENTITY, app.id, 'CREATE',
            f'Integration application created: {app.name}',
            changes={'environment': app.environment, 'scopes': app.scopes},
        )
        return wrap_response(
            _credentials_payload(result),
            status_code=status.HTTP_201_CREATED,
            message='Integration application created.',
        )


class IntegrationApplicationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember]

    def get(self, request, pk: uuid.UUID):
        result = GetIntegrationApplicationUseCase(_repo()).execute(pk)
        return wrap_response(result.model_dump(mode='json'))

    @validated_body(UpdateIntegrationApplicationBody)
    def patch(self, request, pk: uuid.UUID, *, body: dict):
        schema = parse_update_integration_application_schema(**body)
        result = UpdateIntegrationApplicationUseCase(_repo(), _actor_scopes(request)).execute(pk, schema)
        audit_log(
            request, _ENTITY, pk, 'UPDATE',
            f'Integration application updated: {result.name}',
            changes=schema.model_dump(exclude_none=True),
        )
        return wrap_response(result.model_dump(mode='json'), message='Integration application updated.')

    def delete(self, request, pk: uuid.UUID):
        removed = DeleteIntegrationApplicationUseCase(_repo()).execute(pk)
        audit_log(
            request, _ENTITY, pk, 'DELETE',
            f'Integration application deleted: {removed.name}',
            changes={'client_id': removed.client_id},
        )
        return wrap_response(None, message='Integration application deleted.')


class _LifecycleView(APIView):
    """POST-only status transition without body."""

    permission_classes = [IsAuthenticated, IsCompanyMember]
    use_case_class: type
    event_type: str
    message: str

    def post(self, request, pk: uuid.UUID):
        result = self.use_case_class(_repo()).execute(pk)
        security_log(request, event_type=self.event_type, resource=_ENTITY, detail=f'app_id={pk}')
        return wrap_response(result.model_dump(mode='json'), message=self.message)


class IntegrationApplicationEnableView(_LifecycleView):
    use_case_class = EnableIntegrationApplicationUseCase
    event_type = 'integration_oauth_app_enabled'
    message = 'Integration application enabled.'


class IntegrationApplicationDisableView(_LifecycleView):
    use_case_class = DisableIntegrationApplicationUseCase
    event_type = 'integration_oauth_app_disabled'
    message = 'Integration application disabled.'


class IntegrationApplicationRevokeView(_LifecycleView):
    use_case_class = RevokeIntegrationApplicationUseCase
    event_type = 'integration_oauth_app_revoked'
    message = 'Integration application revoked.'


class IntegrationApplicationRotateSecretView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyMember]

    def post(self, request, pk: uuid.UUID):
        result = RotateIntegrationApplicationSecretUseCase(_repo(), _credentials()).execute(pk)
        security_log(
            request,
            event_type='integration_oauth_secret_rotated',
            resource=_ENTITY,
            detail=f'app_id={pk}',
        )
        return wrap_response(_credentials_payload(result), message='Client secret rotated.')
