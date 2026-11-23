"""Unit tests — Integration Application use cases (lifecycle + token grant)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.test import override_settings

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
    CreateIntegrationApplicationSchema,
    IssueTokenInputSchema,
    UpdateIntegrationApplicationSchema,
)
from client.features.integrations.oauth.client.infrastructure.credentials import SecureCredentialFactory
from core.auth.integration.jwt_service import decode_integration_access_token
from core.errors import AppErrorCode
from core.errors.exceptions import (
    AuthException,
    ConflictException,
    NotFoundException,
    PermissionException,
    ValidationAppException,
)
from core.query.core import PaginatedQuery

from client.tests.unit.integrations.oauth.conftest import FakeScopeCatalog

USE_CASES_MODULE = 'client.features.integrations.oauth.client.application.use_cases'


def _create(repo, credentials, scopes=None, name='ERP bridge', catalog=None):
    return CreateIntegrationApplicationUseCase(repo, credentials, catalog or FakeScopeCatalog()).execute(
        CreateIntegrationApplicationSchema(
            name=name,
            description='Sync orders',
            environment='CLIENT_TEST',
            scopes=scopes or ['api.orders.write', 'api.orders.read'],
        ),
        created_by=uuid.uuid4(),
    )


def _token_input(client_id, secret, scope=None):
    return IssueTokenInputSchema(
        grant_type='client_credentials',
        client_id=client_id,
        client_secret=secret,
        scope=scope,
    )


@pytest.mark.unit
class TestCreate:

    def test_returns_secret_once_and_stores_only_digest(self, repo, credentials):
        created = _create(repo, credentials)
        app = created.application
        assert app.status == 'ACTIVE'
        assert app.client_id.startswith('wa_')
        assert app.scopes == ['api.orders.read', 'api.orders.write']
        assert app.secret_prefix == created.client_secret[:8]
        assert repo.secret_hashes[app.id] == f'h:{created.client_secret}'
        assert created.client_secret not in repr(created)

    def test_deduplicates_scopes(self, repo, credentials):
        created = _create(repo, credentials, scopes=['api.orders.read', 'api.orders.read'])
        assert created.application.scopes == ['api.orders.read']

    def test_rejects_non_api_functionality_without_writing(self, repo, credentials):
        with pytest.raises(ValidationAppException) as exc:
            _create(repo, credentials, scopes=['api.orders.read', 'orders.view', 'ai.forecast'])
        assert exc.value.code == AppErrorCode.INT_OAUTH_SCOPE_NOT_API
        assert exc.value.context == {'scopes': ['ai.forecast', 'orders.view']}
        assert repo.writes == 0

    def test_non_api_check_runs_before_plan_check(self, repo, credentials):
        catalog = FakeScopeCatalog(grantable=[])
        with pytest.raises(ValidationAppException) as exc:
            _create(repo, credentials, scopes=['orders.view'], catalog=catalog)
        assert exc.value.code == AppErrorCode.INT_OAUTH_SCOPE_NOT_API

    def test_api_scope_outside_plan_is_not_grantable(self, repo, credentials):
        catalog = FakeScopeCatalog(api=[*FakeScopeCatalog().api, 'api.billing.read'])
        with pytest.raises(PermissionException) as exc:
            _create(repo, credentials, scopes=['api.billing.read'], catalog=catalog)
        assert exc.value.code == AppErrorCode.INT_OAUTH_SCOPE_NOT_GRANTABLE
        assert exc.value.context == {'scopes': ['api.billing.read']}
        assert repo.writes == 0

    def test_rejects_scope_the_role_cannot_grant(self, repo, credentials):
        catalog = FakeScopeCatalog(grantable=['api.orders.read'])
        with pytest.raises(PermissionException) as exc:
            _create(repo, credentials, scopes=['api.orders.write'], catalog=catalog)
        assert exc.value.code == AppErrorCode.INT_OAUTH_SCOPE_NOT_GRANTABLE
        assert repo.writes == 0

    def test_rejects_scope_outside_tenant_plan(self, repo, credentials):
        catalog = FakeScopeCatalog(tenant=['api.orders.read'], grantable=['api.orders.read', 'api.orders.write'])
        with pytest.raises(PermissionException):
            _create(repo, credentials, scopes=['api.orders.write'], catalog=catalog)

    def test_blank_scopes_are_invalid(self, repo, credentials):
        schema = CreateIntegrationApplicationSchema.model_construct(
            name='App', description='', environment='CLIENT_TEST', scopes=['  '],
        )
        with pytest.raises(ValidationAppException) as exc:
            CreateIntegrationApplicationUseCase(repo, credentials, FakeScopeCatalog()).execute(schema)
        assert exc.value.code == AppErrorCode.INT_OAUTH_INVALID_SCOPE

    def test_works_with_real_secure_factory(self, repo):
        created = _create(repo, SecureCredentialFactory())
        digest = repo.secret_hashes[created.application.id]
        assert digest.startswith('sha256$')
        assert created.client_secret not in digest


@pytest.mark.unit
class TestReadUseCases:

    def test_list_unpaginated(self, repo, credentials):
        _create(repo, credentials, name='B app')
        _create(repo, credentials, name='A app')
        query = PaginatedQuery(page=0, page_size=0, filters={}, unpaginated=True)
        listed = ListIntegrationApplicationsUseCase(repo).execute(query)
        assert [a.name for a in listed.items] == ['A app', 'B app']

    def test_get(self, repo, credentials):
        created = _create(repo, credentials)
        got = GetIntegrationApplicationUseCase(repo).execute(created.application.id)
        assert got.client_id == created.application.client_id

    def test_get_missing_raises_not_found(self, repo):
        with pytest.raises(NotFoundException) as exc:
            GetIntegrationApplicationUseCase(repo).execute(uuid.uuid4())
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_NOT_FOUND

    def test_list_grantable_scopes(self):
        catalog = FakeScopeCatalog(grantable=['api.orders.read', 'api.inventories.read'])
        keys = [s.key for s in ListGrantableIntegrationScopesUseCase(catalog).execute()]
        assert keys == ['api.orders.read', 'api.inventories.read']

    def test_list_grantable_scopes_empty_without_plan(self):
        assert ListGrantableIntegrationScopesUseCase(FakeScopeCatalog(tenant=[])).execute() == []


@pytest.mark.unit
class TestUpdate:

    def test_updates_metadata_and_scopes(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        updated = UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
            app_id,
            UpdateIntegrationApplicationSchema(name='Renamed', scopes=['api.inventories.read']),
        )
        assert updated.name == 'Renamed'
        assert updated.scopes == ['api.inventories.read']

    def test_disabled_app_is_editable(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        DisableIntegrationApplicationUseCase(repo).execute(app_id)
        updated = UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
            app_id, UpdateIntegrationApplicationSchema(environment='CLIENT_PROD'),
        )
        assert updated.environment == 'CLIENT_PROD'
        assert updated.status == 'DISABLED'

    def test_empty_patch_is_a_no_op(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        writes = repo.writes
        result = UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
            app_id, UpdateIntegrationApplicationSchema(),
        )
        assert result.id == app_id
        assert repo.writes == writes

    def test_non_api_scope_rejected(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        writes = repo.writes
        with pytest.raises(ValidationAppException) as exc:
            UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
                app_id, UpdateIntegrationApplicationSchema(scopes=['admin.all']),
            )
        assert exc.value.code == AppErrorCode.INT_OAUTH_SCOPE_NOT_API
        assert repo.writes == writes

    def test_legacy_non_api_scopes_cannot_be_kept(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        repo.apps[app_id] = repo.apps[app_id].model_copy(update={'scopes': ['api.orders.read', 'orders:read']})
        with pytest.raises(ValidationAppException) as exc:
            UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
                app_id, UpdateIntegrationApplicationSchema(scopes=['api.orders.read', 'orders:read']),
            )
        assert exc.value.code == AppErrorCode.INT_OAUTH_SCOPE_NOT_API
        assert exc.value.context == {'scopes': ['orders:read']}

    def test_dropping_legacy_scopes_is_allowed(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        repo.apps[app_id] = repo.apps[app_id].model_copy(update={'scopes': ['api.orders.read', 'orders:read']})
        updated = UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
            app_id, UpdateIntegrationApplicationSchema(scopes=['api.orders.read']),
        )
        assert updated.scopes == ['api.orders.read']

    def test_keeps_already_granted_scopes_the_editor_cannot_grant(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        limited = FakeScopeCatalog(grantable=['api.inventories.read'])
        updated = UpdateIntegrationApplicationUseCase(repo, limited).execute(
            app_id,
            UpdateIntegrationApplicationSchema(scopes=['api.orders.read', 'api.inventories.read']),
        )
        assert updated.scopes == ['api.inventories.read', 'api.orders.read']

    def test_editor_cannot_add_scopes_beyond_role(self, repo, credentials):
        app_id = _create(repo, credentials, scopes=['api.orders.read']).application.id
        limited = FakeScopeCatalog(grantable=['api.orders.read'])
        with pytest.raises(PermissionException):
            UpdateIntegrationApplicationUseCase(repo, limited).execute(
                app_id, UpdateIntegrationApplicationSchema(scopes=['api.orders.read', 'api.orders.write']),
            )

    def test_missing_app(self, repo):
        with pytest.raises(NotFoundException):
            UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
                uuid.uuid4(), UpdateIntegrationApplicationSchema(name='Xy'),
            )

    def test_revoked_app_rejected(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        RevokeIntegrationApplicationUseCase(repo).execute(app_id)
        with pytest.raises(ConflictException) as exc:
            UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
                app_id, UpdateIntegrationApplicationSchema(name='Xy'),
            )
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_REVOKED

    def test_lost_race_reports_state_changed(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        repo.force_lost_race = True
        with pytest.raises(ConflictException) as exc:
            UpdateIntegrationApplicationUseCase(repo, FakeScopeCatalog()).execute(
                app_id, UpdateIntegrationApplicationSchema(name='Xy'),
            )
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_STATE_CHANGED


@pytest.mark.unit
class TestEnableDisable:

    def test_disable_then_enable(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        assert DisableIntegrationApplicationUseCase(repo).execute(app_id).status == 'DISABLED'
        assert EnableIntegrationApplicationUseCase(repo).execute(app_id).status == 'ACTIVE'

    def test_transitions_are_idempotent(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        writes = repo.writes
        assert EnableIntegrationApplicationUseCase(repo).execute(app_id).status == 'ACTIVE'
        assert repo.writes == writes
        DisableIntegrationApplicationUseCase(repo).execute(app_id)
        writes = repo.writes
        assert DisableIntegrationApplicationUseCase(repo).execute(app_id).status == 'DISABLED'
        assert repo.writes == writes

    @pytest.mark.parametrize('use_case', [
        EnableIntegrationApplicationUseCase,
        DisableIntegrationApplicationUseCase,
    ])
    def test_revoked_is_terminal(self, repo, credentials, use_case):
        app_id = _create(repo, credentials).application.id
        RevokeIntegrationApplicationUseCase(repo).execute(app_id)
        with pytest.raises(ConflictException) as exc:
            use_case(repo).execute(app_id)
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_REVOKED

    def test_missing_app(self, repo):
        with pytest.raises(NotFoundException):
            DisableIntegrationApplicationUseCase(repo).execute(uuid.uuid4())

    def test_concurrent_revoke_surfaces_revoked(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        original_get = repo.get_by_id
        calls = {'n': 0}

        def racing_get(target_id):
            calls['n'] += 1
            snapshot = original_get(target_id)
            if calls['n'] == 1:
                repo.set_raw_status(target_id, 'REVOKED')
            return snapshot

        repo.get_by_id = racing_get
        with pytest.raises(ConflictException) as exc:
            DisableIntegrationApplicationUseCase(repo).execute(app_id)
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_REVOKED

    def test_app_deleted_mid_flight_is_not_found(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        original_get = repo.get_by_id
        calls = {'n': 0}

        def vanishing_get(target_id):
            calls['n'] += 1
            snapshot = original_get(target_id)
            if calls['n'] == 1:
                repo.apps.pop(target_id)
            return snapshot

        repo.get_by_id = vanishing_get
        with pytest.raises(NotFoundException):
            DisableIntegrationApplicationUseCase(repo).execute(app_id)


@pytest.mark.unit
class TestRevoke:

    def test_revoke_invalidates_secret(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        revoked = RevokeIntegrationApplicationUseCase(repo).execute(app_id)
        assert revoked.status == 'REVOKED'
        assert revoked.secret_prefix is None
        assert repo.get_active_secret_hash(app_id) is None

    def test_revoke_from_disabled(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        DisableIntegrationApplicationUseCase(repo).execute(app_id)
        assert RevokeIntegrationApplicationUseCase(repo).execute(app_id).status == 'REVOKED'

    def test_revoke_is_idempotent(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        RevokeIntegrationApplicationUseCase(repo).execute(app_id)
        writes = repo.writes
        assert RevokeIntegrationApplicationUseCase(repo).execute(app_id).status == 'REVOKED'
        assert repo.writes == writes

    def test_revoke_missing(self, repo):
        with pytest.raises(NotFoundException):
            RevokeIntegrationApplicationUseCase(repo).execute(uuid.uuid4())

    def test_concurrent_revoke_returns_revoked(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        original_revoke = repo.revoke

        def racing_revoke(target_id, **kwargs):
            original_revoke(target_id, **kwargs)
            return None

        repo.revoke = racing_revoke
        assert RevokeIntegrationApplicationUseCase(repo).execute(app_id).status == 'REVOKED'

    def test_lost_race_without_revoke_is_conflict(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        repo.force_lost_race = True
        with pytest.raises(ConflictException) as exc:
            RevokeIntegrationApplicationUseCase(repo).execute(app_id)
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_STATE_CHANGED


@pytest.mark.unit
class TestRotateSecret:

    def test_rotate_returns_new_secret(self, repo, credentials):
        created = _create(repo, credentials)
        rotated = RotateIntegrationApplicationSecretUseCase(repo, credentials).execute(
            created.application.id,
        )
        assert rotated.client_secret != created.client_secret
        assert rotated.application.secret_prefix == rotated.client_secret[:8]
        assert repo.secret_versions[created.application.id] == 2

    def test_rotate_disabled_app_allowed(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        DisableIntegrationApplicationUseCase(repo).execute(app_id)
        rotated = RotateIntegrationApplicationSecretUseCase(repo, credentials).execute(app_id)
        assert rotated.application.status == 'DISABLED'

    def test_rotate_revoked_app_conflicts(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        RevokeIntegrationApplicationUseCase(repo).execute(app_id)
        with pytest.raises(ConflictException) as exc:
            RotateIntegrationApplicationSecretUseCase(repo, credentials).execute(app_id)
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_REVOKED

    def test_rotate_missing(self, repo, credentials):
        with pytest.raises(NotFoundException):
            RotateIntegrationApplicationSecretUseCase(repo, credentials).execute(uuid.uuid4())

    def test_rotate_lost_race(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        repo.force_lost_race = True
        with pytest.raises(ConflictException) as exc:
            RotateIntegrationApplicationSecretUseCase(repo, credentials).execute(app_id)
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_STATE_CHANGED


@pytest.mark.unit
class TestDelete:

    def test_delete_revoked_app(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        RevokeIntegrationApplicationUseCase(repo).execute(app_id)
        removed = DeleteIntegrationApplicationUseCase(repo).execute(app_id)
        assert removed.id == app_id
        assert repo.get_by_id(app_id) is None

    @pytest.mark.parametrize('disable_first', [False, True])
    def test_delete_requires_revoke(self, repo, credentials, disable_first):
        app_id = _create(repo, credentials).application.id
        if disable_first:
            DisableIntegrationApplicationUseCase(repo).execute(app_id)
        with pytest.raises(ConflictException) as exc:
            DeleteIntegrationApplicationUseCase(repo).execute(app_id)
        assert exc.value.code == AppErrorCode.INT_OAUTH_APP_NOT_REVOKED
        assert repo.get_by_id(app_id) is not None

    def test_delete_missing(self, repo):
        with pytest.raises(NotFoundException):
            DeleteIntegrationApplicationUseCase(repo).execute(uuid.uuid4())

    def test_delete_lost_race(self, repo, credentials):
        app_id = _create(repo, credentials).application.id
        RevokeIntegrationApplicationUseCase(repo).execute(app_id)
        repo.force_lost_race = True
        with pytest.raises(NotFoundException):
            DeleteIntegrationApplicationUseCase(repo).execute(app_id)


@pytest.mark.unit
class TestIssueClientCredentialsToken:

    def _issue(self, repo, credentials, data, catalog=None):
        with override_settings(INTEGRATION_JWT_SECRET='int-secret'), patch(
            f'{USE_CASES_MODULE}.connection',
        ) as conn:
            conn.schema_name = 'tenant_acme'
            return IssueClientCredentialsTokenUseCase(
                repo, credentials, catalog or FakeScopeCatalog(),
            ).execute(data)

    def test_scopes_dropped_from_plan_are_not_issued(self, repo, credentials):
        created = _create(repo, credentials)
        downgraded = FakeScopeCatalog(tenant=['api.orders.read'])
        token = self._issue(
            repo, credentials,
            _token_input(created.application.client_id, created.client_secret),
            catalog=downgraded,
        )
        assert token.scope == 'api.orders.read'

    def test_requesting_scope_dropped_from_plan_is_denied(self, repo, credentials):
        created = _create(repo, credentials)
        downgraded = FakeScopeCatalog(tenant=['api.orders.read'])
        with pytest.raises(AuthException) as exc:
            self._issue(
                repo, credentials,
                _token_input(created.application.client_id, created.client_secret, 'api.orders.write'),
                catalog=downgraded,
            )
        assert exc.value.code == AppErrorCode.AUTH_SCOPE_DENIED

    def test_no_available_scope_is_denied(self, repo, credentials):
        created = _create(repo, credentials)
        with pytest.raises(AuthException) as exc:
            self._issue(
                repo, credentials,
                _token_input(created.application.client_id, created.client_secret),
                catalog=FakeScopeCatalog(tenant=[]),
            )
        assert exc.value.code == AppErrorCode.AUTH_SCOPE_DENIED
        assert repo.apps[created.application.id].last_used_at is None

    def test_issues_token_with_all_granted_scopes(self, repo, credentials):
        created = _create(repo, credentials)
        token = self._issue(
            repo, credentials,
            _token_input(created.application.client_id, created.client_secret),
        )
        assert token.token_type == 'Bearer'
        assert token.expires_in > 0
        with override_settings(INTEGRATION_JWT_SECRET='int-secret'):
            payload = decode_integration_access_token(token.access_token)
        assert payload['user_type'] == 'integration'
        assert payload['client_id'] == created.application.client_id
        assert set(payload['scopes']) == {'api.orders.read', 'api.orders.write'}
        assert payload['schema_name'] == 'tenant_acme'
        assert repo.apps[created.application.id].last_used_at is not None

    def test_subset_scope_request(self, repo, credentials):
        created = _create(repo, credentials)
        token = self._issue(
            repo, credentials,
            _token_input(created.application.client_id, created.client_secret, 'api.orders.read'),
        )
        assert token.scope == 'api.orders.read'

    def test_denied_scope(self, repo, credentials):
        created = _create(repo, credentials, scopes=['api.orders.read'])
        with pytest.raises(AuthException) as exc:
            IssueClientCredentialsTokenUseCase(repo, credentials, FakeScopeCatalog()).execute(
                _token_input(created.application.client_id, created.client_secret, 'api.orders.write'),
            )
        assert exc.value.code == AppErrorCode.AUTH_SCOPE_DENIED

    def test_bad_secret(self, repo, credentials):
        created = _create(repo, credentials)
        with pytest.raises(AuthException) as exc:
            IssueClientCredentialsTokenUseCase(repo, credentials, FakeScopeCatalog()).execute(
                _token_input(created.application.client_id, 'wrong-secret-value!!'),
            )
        assert exc.value.code == AppErrorCode.AUTH_INVALID_CREDENTIALS

    def test_unknown_client(self, repo, credentials):
        with pytest.raises(AuthException) as exc:
            IssueClientCredentialsTokenUseCase(repo, credentials, FakeScopeCatalog()).execute(
                _token_input('wa_unknown', 'x' * 32),
            )
        assert exc.value.code == AppErrorCode.AUTH_INVALID_CREDENTIALS

    def test_disabled_app_cannot_mint(self, repo, credentials):
        created = _create(repo, credentials)
        DisableIntegrationApplicationUseCase(repo).execute(created.application.id)
        with pytest.raises(AuthException) as exc:
            IssueClientCredentialsTokenUseCase(repo, credentials, FakeScopeCatalog()).execute(
                _token_input(created.application.client_id, created.client_secret),
            )
        assert exc.value.code == AppErrorCode.AUTH_APP_INACTIVE

    def test_disabled_app_hides_status_from_bad_secret(self, repo, credentials):
        created = _create(repo, credentials)
        DisableIntegrationApplicationUseCase(repo).execute(created.application.id)
        with pytest.raises(AuthException) as exc:
            IssueClientCredentialsTokenUseCase(repo, credentials, FakeScopeCatalog()).execute(
                _token_input(created.application.client_id, 'wrong-secret-value!!'),
            )
        assert exc.value.code == AppErrorCode.AUTH_INVALID_CREDENTIALS

    def test_revoked_app_credentials_are_dead(self, repo, credentials):
        created = _create(repo, credentials)
        RevokeIntegrationApplicationUseCase(repo).execute(created.application.id)
        with pytest.raises(AuthException) as exc:
            IssueClientCredentialsTokenUseCase(repo, credentials, FakeScopeCatalog()).execute(
                _token_input(created.application.client_id, created.client_secret),
            )
        assert exc.value.code == AppErrorCode.AUTH_INVALID_CREDENTIALS

    def test_reenabled_app_mints_again(self, repo, credentials):
        created = _create(repo, credentials)
        DisableIntegrationApplicationUseCase(repo).execute(created.application.id)
        EnableIntegrationApplicationUseCase(repo).execute(created.application.id)
        token = self._issue(
            repo, credentials,
            _token_input(created.application.client_id, created.client_secret),
        )
        assert token.access_token

    def test_rotated_secret_invalidates_old(self, repo, credentials):
        created = _create(repo, credentials)
        rotated = RotateIntegrationApplicationSecretUseCase(repo, credentials).execute(
            created.application.id,
        )
        with pytest.raises(AuthException):
            IssueClientCredentialsTokenUseCase(repo, credentials, FakeScopeCatalog()).execute(
                _token_input(created.application.client_id, created.client_secret),
            )
        token = self._issue(
            repo, credentials,
            _token_input(created.application.client_id, rotated.client_secret),
        )
        assert token.access_token
