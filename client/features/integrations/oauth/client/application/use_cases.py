"""Use cases for Integration Application lifecycle and token issuance.

Input shape is enforced by Pydantic domain schemas at the presentation
boundary. Use cases apply business rules: grantable scopes (API
functionalities of the tenant plan and the actor's role), status machine,
credential minting/verification. Every write is a compare-and-set in the
repository; a lost race is reported as a conflict, never silently applied.
"""
from __future__ import annotations

import uuid
from typing import Iterable

from django.db import connection

from client.features.integrations.oauth.client.domain import lifecycle
from client.features.integrations.oauth.client.domain.interfaces import (
    ICredentialFactory,
    IIntegrationApplicationRepository,
    IIntegrationScopeCatalog,
)
from client.features.integrations.oauth.client.domain.schemas import (
    CreateIntegrationApplicationSchema,
    CreatedApplicationCredentialsSchema,
    IntegrationApplicationSchema,
    IntegrationScopeSchema,
    IssueTokenInputSchema,
    IssuedTokenSchema,
    UpdateIntegrationApplicationSchema,
)
from client.features.integrations.oauth.client.domain.scopes import (
    disallowed_scopes,
    normalize_scope_keys,
    parse_scope_string,
)
from core.auth.integration.jwt_service import (
    create_integration_access_token,
    get_integration_access_ttl_seconds,
    normalize_scopes,
)
from core.errors import (
    AppErrorCode,
    AppException,
    AuthException,
    ConflictException,
    NotFoundException,
    PermissionException,
    ValidationAppException,
)
from core.trace import trace_layer


def _grantable_scopes(
    scopes: Iterable[str],
    allowed: Iterable[str],
    catalog: IIntegrationScopeCatalog,
) -> list[str]:
    """Only API-category functionalities may be linked; then plan/role decides."""
    cleaned = normalize_scope_keys(scopes)
    if not cleaned:
        raise ValidationAppException(AppErrorCode.INT_OAUTH_INVALID_SCOPE)
    not_api = disallowed_scopes(cleaned, catalog.api_scope_keys(cleaned))
    if not_api:
        raise ValidationAppException(
            AppErrorCode.INT_OAUTH_SCOPE_NOT_API,
            context={'scopes': not_api},
        )
    denied = disallowed_scopes(cleaned, allowed)
    if denied:
        raise PermissionException(
            AppErrorCode.INT_OAUTH_SCOPE_NOT_GRANTABLE,
            context={'scopes': denied},
        )
    return cleaned


def _keys(scopes: Iterable[IntegrationScopeSchema]) -> set[str]:
    return {scope.key for scope in scopes}


class _ApplicationUseCase:
    def __init__(self, repository: IIntegrationApplicationRepository):
        self.repository = repository

    def _require(self, app_id: uuid.UUID) -> IntegrationApplicationSchema:
        app = self.repository.get_by_id(app_id)
        if app is None:
            raise NotFoundException(AppErrorCode.INT_OAUTH_APP_NOT_FOUND)
        return app

    def _lost_race(self, app_id: uuid.UUID) -> AppException:
        fresh = self.repository.get_by_id(app_id)
        if fresh is None:
            return NotFoundException(AppErrorCode.INT_OAUTH_APP_NOT_FOUND)
        if fresh.status == lifecycle.REVOKED:
            return ConflictException(AppErrorCode.INT_OAUTH_APP_REVOKED)
        return ConflictException(AppErrorCode.INT_OAUTH_APP_STATE_CHANGED)


class ListGrantableIntegrationScopesUseCase:
    """API functionalities the acting user may grant (plan ∩ role)."""

    def __init__(self, scopes: IIntegrationScopeCatalog):
        self.scopes = scopes

    @trace_layer('application')
    def execute(self) -> list[IntegrationScopeSchema]:
        return self.scopes.grantable_scopes()


class CreateIntegrationApplicationUseCase:
    def __init__(
        self,
        repository: IIntegrationApplicationRepository,
        credentials: ICredentialFactory,
        scopes: IIntegrationScopeCatalog,
    ):
        self.repository = repository
        self.credentials = credentials
        self.scopes = scopes

    @trace_layer('application')
    def execute(
        self,
        data: CreateIntegrationApplicationSchema,
        *,
        created_by: uuid.UUID | None = None,
    ) -> CreatedApplicationCredentialsSchema:
        granted = _grantable_scopes(data.scopes, _keys(self.scopes.grantable_scopes()), self.scopes)
        payload = data.model_copy(update={'scopes': granted})
        secret = self.credentials.new_secret()
        app = self.repository.create(
            payload,
            client_id=self.credentials.new_client_id(),
            secret_hash=secret.digest,
            secret_prefix=secret.prefix,
            created_by=created_by,
        )
        return CreatedApplicationCredentialsSchema(application=app, client_secret=secret.raw)


class ListIntegrationApplicationsUseCase(_ApplicationUseCase):

    @trace_layer('application')
    def execute(self, query):
        return self.repository.list_all(query)


class GetIntegrationApplicationUseCase(_ApplicationUseCase):

    @trace_layer('application')
    def execute(self, app_id: uuid.UUID) -> IntegrationApplicationSchema:
        return self._require(app_id)


class UpdateIntegrationApplicationUseCase(_ApplicationUseCase):
    """Granted API scopes may be kept even if the editor could not grant them; non-API ones never."""

    def __init__(
        self,
        repository: IIntegrationApplicationRepository,
        scopes: IIntegrationScopeCatalog,
    ):
        super().__init__(repository)
        self.scopes = scopes

    @trace_layer('application')
    def execute(
        self,
        app_id: uuid.UUID,
        data: UpdateIntegrationApplicationSchema,
    ) -> IntegrationApplicationSchema:
        current = self._require(app_id)
        lifecycle.ensure_mutable(current.status)
        if not data.has_changes():
            return current

        payload = data
        if data.scopes is not None:
            allowed = _keys(self.scopes.grantable_scopes()) | set(current.scopes)
            payload = data.model_copy(
                update={'scopes': _grantable_scopes(data.scopes, allowed, self.scopes)},
            )

        app = self.repository.update(app_id, payload, allowed_from=lifecycle.MUTABLE_STATUSES)
        if app is None:
            raise self._lost_race(app_id)
        return app


class _ChangeStatusUseCase(_ApplicationUseCase):
    """Idempotent ACTIVE ⇄ DISABLED transition."""

    target: str

    @trace_layer('application')
    def execute(self, app_id: uuid.UUID) -> IntegrationApplicationSchema:
        current = self._require(app_id)
        if current.status == self.target:
            return current
        lifecycle.ensure_mutable(current.status)

        app = self.repository.change_status(
            app_id,
            target=self.target,
            allowed_from=lifecycle.TRANSITION_SOURCES[self.target],
        )
        if app is None:
            raise self._lost_race(app_id)
        return app


class EnableIntegrationApplicationUseCase(_ChangeStatusUseCase):
    target = lifecycle.ACTIVE


class DisableIntegrationApplicationUseCase(_ChangeStatusUseCase):
    target = lifecycle.DISABLED


class RevokeIntegrationApplicationUseCase(_ApplicationUseCase):
    """Terminal: blocks new tokens and invalidates every secret. Idempotent."""

    @trace_layer('application')
    def execute(self, app_id: uuid.UUID) -> IntegrationApplicationSchema:
        current = self._require(app_id)
        if current.status == lifecycle.REVOKED:
            return current

        app = self.repository.revoke(
            app_id,
            target=lifecycle.REVOKED,
            allowed_from=lifecycle.TRANSITION_SOURCES[lifecycle.REVOKED],
        )
        if app is None:
            fresh = self._require(app_id)
            if fresh.status == lifecycle.REVOKED:
                return fresh
            raise ConflictException(AppErrorCode.INT_OAUTH_APP_STATE_CHANGED)
        return app


class RotateIntegrationApplicationSecretUseCase(_ApplicationUseCase):
    def __init__(
        self,
        repository: IIntegrationApplicationRepository,
        credentials: ICredentialFactory,
    ):
        super().__init__(repository)
        self.credentials = credentials

    @trace_layer('application')
    def execute(self, app_id: uuid.UUID) -> CreatedApplicationCredentialsSchema:
        current = self._require(app_id)
        lifecycle.ensure_mutable(current.status)

        secret = self.credentials.new_secret()
        app = self.repository.rotate_secret(
            app_id,
            secret_hash=secret.digest,
            secret_prefix=secret.prefix,
            allowed_from=lifecycle.MUTABLE_STATUSES,
        )
        if app is None:
            raise self._lost_race(app_id)
        return CreatedApplicationCredentialsSchema(application=app, client_secret=secret.raw)


class DeleteIntegrationApplicationUseCase(_ApplicationUseCase):
    """Only revoked apps can be removed, so no live credential disappears silently."""

    @trace_layer('application')
    def execute(self, app_id: uuid.UUID) -> IntegrationApplicationSchema:
        current = self._require(app_id)
        lifecycle.ensure_deletable(current.status)
        if not self.repository.delete(app_id, allowed_from=lifecycle.DELETABLE_STATUSES):
            raise NotFoundException(AppErrorCode.INT_OAUTH_APP_NOT_FOUND)
        return current


class IssueClientCredentialsTokenUseCase:
    """OAuth 2.0 client_credentials grant for Integration Applications.

    Effective scopes are the app's grants still enabled by the tenant plan, so
    a downgrade or a deactivated API functionality takes effect on next token.
    """

    def __init__(
        self,
        repository: IIntegrationApplicationRepository,
        credentials: ICredentialFactory,
        scopes: IIntegrationScopeCatalog,
    ):
        self.repository = repository
        self.credentials = credentials
        self.scopes = scopes

    @trace_layer('application')
    def execute(self, data: IssueTokenInputSchema) -> IssuedTokenSchema:
        app = self.repository.get_by_client_id(data.client_id)
        if app is None:
            raise AuthException(AppErrorCode.AUTH_INVALID_CREDENTIALS)

        secret_hash = self.repository.get_active_secret_hash(app.id)
        if not secret_hash or not self.credentials.verify_secret(data.client_secret, secret_hash):
            raise AuthException(AppErrorCode.AUTH_INVALID_CREDENTIALS)

        if app.status != lifecycle.ACTIVE:
            raise AuthException(AppErrorCode.AUTH_APP_INACTIVE)

        granted = set(app.scopes) & _keys(self.scopes.tenant_scopes())
        requested = parse_scope_string(data.scope)
        if requested:
            denied = [s for s in requested if s not in granted]
            if denied:
                raise AuthException(
                    AppErrorCode.AUTH_SCOPE_DENIED,
                    override_detail=(
                        'Requested scope is not granted to this application: '
                        + ', '.join(denied)
                    ),
                )
            effective = normalize_scopes(requested)
        else:
            effective = normalize_scopes(granted)
        if not effective:
            raise AuthException(
                AppErrorCode.AUTH_SCOPE_DENIED,
                override_detail='None of the scopes granted to this application are currently available.',
            )

        schema_name = getattr(connection, 'schema_name', None) or 'public'
        token, _payload = create_integration_access_token(
            app_id=str(app.id),
            client_id=app.client_id,
            schema_name=schema_name,
            scopes=effective,
        )
        self.repository.touch_last_used(app.id)

        return IssuedTokenSchema(
            access_token=token,
            token_type='Bearer',
            expires_in=get_integration_access_ttl_seconds(),
            scope=' '.join(effective),
        )
