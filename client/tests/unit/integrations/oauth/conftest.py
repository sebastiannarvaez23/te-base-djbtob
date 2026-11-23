"""In-memory adapters for Integration Application OAuth unit tests."""
from __future__ import annotations

import copy
import itertools
import uuid
from datetime import datetime, timezone
from typing import Optional

import pytest

from core.ids import uuid7
from core.query.core import PaginatedQuery, PaginatedResult

from client.features.integrations.oauth.client.domain.interfaces import (
    ICredentialFactory,
    IIntegrationApplicationRepository,
    IIntegrationScopeCatalog,
)
from client.features.integrations.oauth.client.domain.schemas import (
    CreateIntegrationApplicationSchema,
    GeneratedSecretSchema,
    IntegrationApplicationSchema,
    IntegrationScopeSchema,
    UpdateIntegrationApplicationSchema,
)

API_SCOPES = (
    'api.orders.read',
    'api.orders.write',
    'api.inventories.read',
    'api.inventories.write',
    'api.third-parties.read',
    'api.third-parties.write',
)


def scope(key: str) -> IntegrationScopeSchema:
    module = key.split('.')[1]
    return IntegrationScopeSchema(key=key, label=key, module=module, module_name=module.title())


class FakeScopeCatalog(IIntegrationScopeCatalog):
    """``tenant`` = plan-enabled API keys; ``grantable`` = tenant ∩ actor role;
    ``api`` = every key registered as an API-category functionality."""

    def __init__(self, tenant=API_SCOPES, grantable=None, api=None):
        self.tenant = list(tenant)
        self.grantable = list(self.tenant if grantable is None else grantable)
        self.api = set(API_SCOPES) | set(self.tenant) | set(self.grantable) if api is None else set(api)

    def api_scope_keys(self, keys) -> set[str]:
        return set(keys) & self.api

    def tenant_scopes(self) -> list[IntegrationScopeSchema]:
        return [scope(k) for k in self.tenant]

    def grantable_scopes(self) -> list[IntegrationScopeSchema]:
        return [scope(k) for k in self.grantable if k in self.tenant]


class FakeCredentialFactory(ICredentialFactory):
    """Deterministic credentials: secret N → ``secret-000N…``, digest ``h:<raw>``."""

    def __init__(self):
        self._seq = itertools.count(1)

    def new_client_id(self) -> str:
        return f'wa_client{next(self._seq):06d}'

    def new_secret(self) -> GeneratedSecretSchema:
        raw = f'secret-{next(self._seq):04d}'.ljust(40, 'x')
        return GeneratedSecretSchema(raw=raw, digest=f'h:{raw}', prefix=raw[:8])

    def verify_secret(self, raw_secret: str, digest: str) -> bool:
        return bool(raw_secret) and digest == f'h:{raw_secret}'


class InMemoryIntegrationApplicationRepository(IIntegrationApplicationRepository):

    def __init__(self):
        self.apps: dict[uuid.UUID, IntegrationApplicationSchema] = {}
        self.secret_hashes: dict[uuid.UUID, Optional[str]] = {}
        self.secret_versions: dict[uuid.UUID, int] = {}
        self.writes = 0
        self.force_lost_race = False

    def list_all(self, query: PaginatedQuery) -> PaginatedResult:
        items = [copy.deepcopy(a) for a in sorted(self.apps.values(), key=lambda a: a.name)]
        if query.unpaginated:
            return PaginatedResult(items=items, total=len(items), page=0, page_size=0, total_pages=1)
        total = len(items)
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items[query.offset: query.offset + query.limit], total=total,
            page=query.page, page_size=query.page_size, total_pages=total_pages,
        )

    def get_by_id(self, app_id: uuid.UUID) -> Optional[IntegrationApplicationSchema]:
        app = self.apps.get(app_id)
        return copy.deepcopy(app) if app else None

    def get_by_client_id(self, client_id: str) -> Optional[IntegrationApplicationSchema]:
        return next(
            (copy.deepcopy(a) for a in self.apps.values() if a.client_id == client_id),
            None,
        )

    def create(
        self,
        data: CreateIntegrationApplicationSchema,
        *,
        client_id: str,
        secret_hash: str,
        secret_prefix: str,
        created_by: uuid.UUID | None,
    ) -> IntegrationApplicationSchema:
        now = datetime.now(timezone.utc)
        app = IntegrationApplicationSchema(
            id=uuid7(),
            name=data.name,
            description=data.description,
            client_id=client_id,
            status='ACTIVE',
            environment=data.environment,
            scopes=sorted(data.scopes),
            secret_prefix=secret_prefix,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.apps[app.id] = app
        self.secret_hashes[app.id] = secret_hash
        self.secret_versions[app.id] = 1
        self.writes += 1
        return copy.deepcopy(app)

    def update(
        self,
        app_id: uuid.UUID,
        data: UpdateIntegrationApplicationSchema,
        *,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        if not self._guard(app_id, allowed_from):
            return None
        changes = data.model_dump(exclude_none=True)
        if 'scopes' in changes:
            changes['scopes'] = sorted(changes['scopes'])
        return self._patch(app_id, **changes)

    def change_status(
        self,
        app_id: uuid.UUID,
        *,
        target: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        if not self._guard(app_id, allowed_from):
            return None
        return self._patch(app_id, status=target)

    def revoke(
        self,
        app_id: uuid.UUID,
        *,
        target: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        if not self._guard(app_id, allowed_from):
            return None
        self.secret_hashes[app_id] = None
        return self._patch(app_id, status=target, secret_prefix=None)

    def rotate_secret(
        self,
        app_id: uuid.UUID,
        *,
        secret_hash: str,
        secret_prefix: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        if not self._guard(app_id, allowed_from):
            return None
        self.secret_hashes[app_id] = secret_hash
        self.secret_versions[app_id] += 1
        return self._patch(app_id, secret_prefix=secret_prefix)

    def delete(self, app_id: uuid.UUID, *, allowed_from: frozenset[str]) -> bool:
        if not self._guard(app_id, allowed_from):
            return False
        del self.apps[app_id]
        self.secret_hashes.pop(app_id, None)
        self.writes += 1
        return True

    def get_active_secret_hash(self, app_id: uuid.UUID) -> Optional[str]:
        return self.secret_hashes.get(app_id)

    def touch_last_used(self, app_id: uuid.UUID) -> None:
        if app_id in self.apps:
            self.apps[app_id] = self.apps[app_id].model_copy(
                update={'last_used_at': datetime.now(timezone.utc)},
            )

    def set_raw_status(self, app_id: uuid.UUID, status: str) -> None:
        """Simulate a concurrent writer changing the row behind the use case."""
        self.apps[app_id] = self.apps[app_id].model_copy(update={'status': status})

    def _guard(self, app_id: uuid.UUID, allowed_from: frozenset[str]) -> bool:
        if self.force_lost_race:
            return False
        app = self.apps.get(app_id)
        return app is not None and app.status in allowed_from

    def _patch(self, app_id: uuid.UUID, **changes) -> IntegrationApplicationSchema:
        changes['updated_at'] = datetime.now(timezone.utc)
        updated = self.apps[app_id].model_copy(update=changes)
        self.apps[app_id] = updated
        self.writes += 1
        return copy.deepcopy(updated)


@pytest.fixture
def repo() -> InMemoryIntegrationApplicationRepository:
    return InMemoryIntegrationApplicationRepository()


@pytest.fixture
def credentials() -> FakeCredentialFactory:
    return FakeCredentialFactory()


@pytest.fixture
def scopes() -> FakeScopeCatalog:
    return FakeScopeCatalog()
