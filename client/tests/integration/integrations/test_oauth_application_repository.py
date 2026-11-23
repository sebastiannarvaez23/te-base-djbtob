"""Integration tests — DjangoIntegrationApplicationRepository (real Postgres)."""
import pytest

from client.features.integrations.oauth.client.application.use_cases import (
    CreateIntegrationApplicationUseCase,
    DeleteIntegrationApplicationUseCase,
    DisableIntegrationApplicationUseCase,
    EnableIntegrationApplicationUseCase,
    IssueClientCredentialsTokenUseCase,
    RevokeIntegrationApplicationUseCase,
    RotateIntegrationApplicationSecretUseCase,
    UpdateIntegrationApplicationUseCase,
)
from client.features.integrations.oauth.client.domain import lifecycle
from client.features.integrations.oauth.client.domain.interfaces import IIntegrationScopeCatalog
from client.features.integrations.oauth.client.domain.schemas import (
    CreateIntegrationApplicationSchema,
    IntegrationScopeSchema,
    IssueTokenInputSchema,
    UpdateIntegrationApplicationSchema,
)
from client.features.integrations.oauth.client.infrastructure.credentials import SecureCredentialFactory
from client.features.integrations.oauth.client.infrastructure.repositories import (
    DjangoIntegrationApplicationRepository,
)
from client.features.integrations.oauth.client.models import (
    IntegrationApplication,
    IntegrationApplicationScope,
    IntegrationApplicationSecret,
)
from core.errors import AuthException
from core.query.core import PaginatedQuery

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]

API_SCOPES = ('api.orders.read', 'api.orders.write', 'api.inventories.read')


class StaticScopeCatalog(IIntegrationScopeCatalog):

    def tenant_scopes(self) -> list[IntegrationScopeSchema]:
        return [
            IntegrationScopeSchema(key=k, label=k, module=k.split('.')[1], module_name=k.split('.')[1])
            for k in API_SCOPES
        ]

    def grantable_scopes(self) -> list[IntegrationScopeSchema]:
        return self.tenant_scopes()

    def api_scope_keys(self, keys) -> set[str]:
        return set(keys) & set(API_SCOPES)


@pytest.fixture
def repo():
    return DjangoIntegrationApplicationRepository()


@pytest.fixture
def credentials():
    return SecureCredentialFactory()


@pytest.fixture
def scopes():
    return StaticScopeCatalog()


@pytest.fixture
def created(repo, credentials, scopes):
    return CreateIntegrationApplicationUseCase(repo, credentials, scopes).execute(
        CreateIntegrationApplicationSchema(name='ERP bridge', scopes=['api.orders.read', 'api.orders.write']),
    )


def test_create_persists_app_secret_and_scopes(created):
    app = IntegrationApplication.objects.get(pk=created.application.id)
    secret = IntegrationApplicationSecret.objects.get(application=app)
    assert app.id.version == 7
    assert secret.is_active and secret.version == 1
    assert secret.secret_hash.startswith('sha256$')
    assert created.client_secret not in secret.secret_hash
    assert created.application.scopes == ['api.orders.read', 'api.orders.write']


def test_list_filters_and_paginates(repo, credentials, scopes, created):
    CreateIntegrationApplicationUseCase(repo, credentials, scopes).execute(
        CreateIntegrationApplicationSchema(
            name='WMS sync', environment='CLIENT_PROD', scopes=['api.inventories.read'],
        ),
    )
    page = repo.list_all(PaginatedQuery(page=1, page_size=1, filters={}))
    assert page.total == 2 and len(page.items) == 1
    prod = repo.list_all(PaginatedQuery(page=0, page_size=0, filters={'environment': 'CLIENT_PROD'}, unpaginated=True))
    assert [a.name for a in prod.items] == ['WMS sync']
    found = repo.list_all(PaginatedQuery(page=0, page_size=0, filters={'q': 'erp'}, unpaginated=True))
    assert [a.name for a in found.items] == ['ERP bridge']


def test_update_diffs_scopes(repo, scopes, created):
    app_id = created.application.id
    kept = IntegrationApplicationScope.objects.get(application_id=app_id, scope='api.orders.read').id
    updated = UpdateIntegrationApplicationUseCase(repo, scopes).execute(
        app_id, UpdateIntegrationApplicationSchema(scopes=['api.orders.read', 'api.inventories.read']),
    )
    assert updated.scopes == ['api.inventories.read', 'api.orders.read']
    assert IntegrationApplicationScope.objects.filter(pk=kept).exists()


def test_update_guarded_by_status(repo, created):
    app_id = created.application.id
    IntegrationApplication.objects.filter(pk=app_id).update(status=lifecycle.REVOKED)
    result = repo.update(
        app_id, UpdateIntegrationApplicationSchema(name='Nope'), allowed_from=lifecycle.MUTABLE_STATUSES,
    )
    assert result is None
    assert IntegrationApplication.objects.get(pk=app_id).name == 'ERP bridge'


def test_rotate_versions_secrets(repo, credentials, created):
    app_id = created.application.id
    rotated = RotateIntegrationApplicationSecretUseCase(repo, credentials).execute(app_id)
    secrets = list(IntegrationApplicationSecret.objects.filter(application_id=app_id).order_by('version'))
    assert [s.version for s in secrets] == [1, 2]
    assert [s.is_active for s in secrets] == [False, True]
    assert secrets[0].revoked_at is not None
    assert rotated.application.secret_prefix == rotated.client_secret[:8]


def test_disable_blocks_token_and_enable_restores(repo, credentials, scopes, created):
    app_id = created.application.id
    token_input = IssueTokenInputSchema(
        grant_type='client_credentials',
        client_id=created.application.client_id,
        client_secret=created.client_secret,
    )
    DisableIntegrationApplicationUseCase(repo).execute(app_id)
    with pytest.raises(AuthException):
        IssueClientCredentialsTokenUseCase(repo, credentials, scopes).execute(token_input)
    EnableIntegrationApplicationUseCase(repo).execute(app_id)
    assert IssueClientCredentialsTokenUseCase(repo, credentials, scopes).execute(token_input).access_token


def test_revoke_invalidates_all_secrets_then_delete(repo, created):
    app_id = created.application.id
    revoked = RevokeIntegrationApplicationUseCase(repo).execute(app_id)
    assert revoked.status == lifecycle.REVOKED
    assert revoked.secret_prefix is None
    assert not IntegrationApplicationSecret.objects.filter(application_id=app_id, is_active=True).exists()

    DeleteIntegrationApplicationUseCase(repo).execute(app_id)
    assert not IntegrationApplication.objects.filter(pk=app_id).exists()
    assert not IntegrationApplicationSecret.objects.filter(application_id=app_id).exists()
    assert not IntegrationApplicationScope.objects.filter(application_id=app_id).exists()


def test_change_status_compare_and_set(repo, created):
    app_id = created.application.id
    assert repo.change_status(app_id, target=lifecycle.ACTIVE, allowed_from=frozenset({lifecycle.DISABLED})) is None
    assert repo.delete(app_id, allowed_from=lifecycle.DELETABLE_STATUSES) is False


def test_touch_last_used(repo, created):
    repo.touch_last_used(created.application.id)
    assert repo.get_by_id(created.application.id).last_used_at is not None
