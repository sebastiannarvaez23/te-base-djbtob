"""Ports for Integration Application OAuth.

Mutating repository methods take ``allowed_from``: the write only applies if
the row is (still) in one of those statuses, under a row lock. ``None`` /
``False`` means "not found or state changed" and the use case resolves which.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Iterable, Optional

from core.query.core import PaginatedQuery, PaginatedResult

from .schemas import (
    CreateIntegrationApplicationSchema,
    GeneratedSecretSchema,
    IntegrationApplicationSchema,
    IntegrationScopeSchema,
    UpdateIntegrationApplicationSchema,
)


class IIntegrationScopeCatalog(ABC):
    """API-category functionalities usable as Integration Application scopes."""

    @abstractmethod
    def tenant_scopes(self) -> list[IntegrationScopeSchema]:
        """Active API functionalities enabled by the tenant's subscription."""

    @abstractmethod
    def grantable_scopes(self) -> list[IntegrationScopeSchema]:
        """``tenant_scopes`` further restricted by the acting user's role."""

    @abstractmethod
    def api_scope_keys(self, keys: Iterable[str]) -> set[str]:
        """Subset of ``keys`` registered as API-category functionalities (any plan or state)."""


class ICredentialFactory(ABC):
    """Mints client identifiers/secrets and verifies presented secrets."""

    @abstractmethod
    def new_client_id(self) -> str:
        ...

    @abstractmethod
    def new_secret(self) -> GeneratedSecretSchema:
        ...

    @abstractmethod
    def verify_secret(self, raw_secret: str, digest: str) -> bool:
        ...


class IIntegrationApplicationRepository(ABC):

    @abstractmethod
    def list_all(self, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def get_by_id(self, app_id: uuid.UUID) -> Optional[IntegrationApplicationSchema]:
        ...

    @abstractmethod
    def get_by_client_id(self, client_id: str) -> Optional[IntegrationApplicationSchema]:
        ...

    @abstractmethod
    def create(
        self,
        data: CreateIntegrationApplicationSchema,
        *,
        client_id: str,
        secret_hash: str,
        secret_prefix: str,
        created_by: uuid.UUID | None,
    ) -> IntegrationApplicationSchema:
        ...

    @abstractmethod
    def update(
        self,
        app_id: uuid.UUID,
        data: UpdateIntegrationApplicationSchema,
        *,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        ...

    @abstractmethod
    def change_status(
        self,
        app_id: uuid.UUID,
        *,
        target: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        ...

    @abstractmethod
    def revoke(
        self,
        app_id: uuid.UUID,
        *,
        target: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        """Set terminal status and invalidate every active secret atomically."""

    @abstractmethod
    def rotate_secret(
        self,
        app_id: uuid.UUID,
        *,
        secret_hash: str,
        secret_prefix: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        ...

    @abstractmethod
    def delete(self, app_id: uuid.UUID, *, allowed_from: frozenset[str]) -> bool:
        ...

    @abstractmethod
    def get_active_secret_hash(self, app_id: uuid.UUID) -> Optional[str]:
        ...

    @abstractmethod
    def touch_last_used(self, app_id: uuid.UUID) -> None:
        ...
