"""Puertos del dominio de integraciones."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from .enums import ConnectorKind, ConnectorProvider
from .schemas import (
    ConnectionProfile,
    ConnectionTestResult,
    DryRunResult,
    SyncRequest,
    SyncResult,
)


class IConnector(ABC):
    """Contrato que todo adaptador de sistema externo debe cumplir."""

    provider: ConnectorProvider
    kind: ConnectorKind
    version: str = '1.0'

    @abstractmethod
    def test_connection(self, profile: ConnectionProfile) -> ConnectionTestResult:
        ...

    @abstractmethod
    def pull_entities(self, request: SyncRequest) -> SyncResult:
        ...

    @abstractmethod
    def push_entities(self, request: SyncRequest) -> SyncResult:
        ...

    @abstractmethod
    def dry_run(self, request: SyncRequest) -> DryRunResult:
        ...


class IConnectorRegistry(ABC):

    @abstractmethod
    def resolve(
        self,
        provider: ConnectorProvider,
        version: str = '1.0',
    ) -> Type[IConnector]:
        ...

    @abstractmethod
    def register(
        self,
        provider: ConnectorProvider,
        cls: Type[IConnector],
        *,
        version: str = '1.0',
    ) -> None:
        ...


class ISecretStore(ABC):
    """Almacén de secretos cifrados (scope = tenant:connection)."""

    @abstractmethod
    def put(self, scope: str, secrets: dict[str, str]) -> str:
        """Persiste secretos; devuelve referencia opaca."""
        ...

    @abstractmethod
    def get(self, ref: str) -> dict[str, str]:
        ...

    @abstractmethod
    def delete(self, ref: str) -> None:
        ...


class IIdempotencyStore(ABC):

    @abstractmethod
    def get(self, scope: str, key: str) -> Optional[dict[str, Any]]:
        ...

    @abstractmethod
    def put(
        self,
        scope: str,
        key: str,
        payload: dict[str, Any],
        *,
        ttl_seconds: int = 86400,
    ) -> None:
        ...
