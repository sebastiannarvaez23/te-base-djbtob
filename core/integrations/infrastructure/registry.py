"""Registro de clases de conector por proveedor y versión."""

from __future__ import annotations

from typing import Type

from core.errors import AppErrorCode
from core.errors.exceptions import ServerException
from core.integrations.domain.enums import ConnectorProvider
from core.integrations.domain.interfaces import IConnector, IConnectorRegistry

_REGISTRY: dict[tuple[str, str], type[IConnector]] = {}


def register_connector(
    provider: ConnectorProvider,
    cls: type[IConnector],
    *,
    version: str = '1.0',
) -> None:
    _REGISTRY[(provider.value, version)] = cls


def get_connector_class(
    provider: ConnectorProvider,
    version: str = '1.0',
) -> type[IConnector] | None:
    return _REGISTRY.get((provider.value, version))


def registered_providers() -> list[ConnectorProvider]:
    seen: set[str] = set()
    result: list[ConnectorProvider] = []
    for key in _REGISTRY:
        if key[0] not in seen:
            seen.add(key[0])
            result.append(ConnectorProvider(key[0]))
    return result


class ConnectorRegistry(IConnectorRegistry):

    def resolve(
        self,
        provider: ConnectorProvider,
        version: str = '1.0',
    ) -> Type[IConnector]:
        cls = get_connector_class(provider, version)
        if cls is None:
            raise ServerException(
                AppErrorCode.INT_CONNECTOR_NOT_FOUND,
                context={'provider': provider.value, 'version': version},
            )
        return cls

    def register(
        self,
        provider: ConnectorProvider,
        cls: Type[IConnector],
        *,
        version: str = '1.0',
    ) -> None:
        register_connector(provider, cls, version=version)
