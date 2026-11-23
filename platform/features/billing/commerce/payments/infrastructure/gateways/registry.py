"""
Registro de adapters de proveedores de pago.

Cuando llegue un proveedor real (Stripe, Wompi, etc.), su adapter debe:

1. Implementar :class:`IPaymentGateway`.
2. Auto-registrarse llamando a :func:`register_gateway` al importarse,
   o ser importado/registrado explícitamente en ``apps.py`` de su feature.

El simulator NO usa el registry — se resuelve de forma directa en la
factory para garantizar que siempre exista, incluso si no hay adapters
reales instalados.
"""

from typing import Optional

from ...domain.enums import GatewayProvider
from ...domain.interfaces import IPaymentGateway


_REGISTRY: dict[GatewayProvider, type[IPaymentGateway]] = {}


def register_gateway(provider: GatewayProvider, cls: type[IPaymentGateway]) -> None:
    """Registra un adapter para un proveedor. Sobrescribe si ya existe."""
    _REGISTRY[provider] = cls


def get_gateway_class(provider: GatewayProvider) -> Optional[type[IPaymentGateway]]:
    """Devuelve la clase del adapter registrada, o ``None`` si no hay."""
    return _REGISTRY.get(provider)


def registered_providers() -> list[GatewayProvider]:
    """Lista los proveedores con adapter activo (excluye simulator)."""
    return list(_REGISTRY.keys())
