"""
Factory de :class:`IPaymentGateway`.

Es la única función que el resto del código debe llamar para obtener un
gateway. Encapsula:

  * la decisión "¿estamos en modo simulado o real?" (parámetro
    ``SIMULATE_PAYMENT`` de plataforma — default ``True``),
  * el lookup del adapter real en el registry cuando no simulamos
    (parámetro ``PAYMENT_PROVIDER`` — sin default, debe configurarse).

Diseño deliberado: en modo simulado se devuelve **siempre** el
:class:`SimulatedGateway`, sin importar qué provider esté configurado.
Esto evita sorpresas en entornos de prueba ("creí que estaba mockeado").
"""

from typing import Optional

from core.parameters import get_parameter

from ...domain.enums import GatewayProvider
from ...domain.interfaces import IPaymentGateway
from .registry import get_gateway_class
from .simulator.gateway import SimulatedGateway


PARAM_SIMULATE_PAYMENT = 'SIMULATE_PAYMENT'
PARAM_PAYMENT_PROVIDER = 'PAYMENT_PROVIDER'


class PaymentGatewayUnavailableError(RuntimeError):
    """No hay adapter disponible para la configuración actual."""


def is_simulation_enabled() -> bool:
    """
    True si los pagos deben simularse.

    Default ``True`` cuando el parámetro no existe — fail-safe para
    entornos de desarrollo. En producción debe configurarse
    explícitamente a ``False`` cuando haya un proveedor real cableado.
    """
    return bool(get_parameter(PARAM_SIMULATE_PAYMENT, default=True))


def configured_provider() -> Optional[GatewayProvider]:
    """Lee el provider configurado en el parámetro de plataforma."""
    raw = get_parameter(PARAM_PAYMENT_PROVIDER)
    if not raw:
        return None
    try:
        return GatewayProvider(str(raw).lower())
    except ValueError:
        return None


def get_payment_gateway(provider: Optional[GatewayProvider] = None) -> IPaymentGateway:
    """
    Devuelve el adapter de gateway a usar para la próxima operación.

    Algoritmo:
      1. Si ``SIMULATE_PAYMENT=True`` ⇒ :class:`SimulatedGateway`.
      2. Si se pasa ``provider`` explícito ⇒ se busca en el registry.
      3. Si no, se lee ``PAYMENT_PROVIDER`` de parámetros.
      4. Si nada de eso resuelve ⇒
         :class:`PaymentGatewayUnavailableError`.
    """

    if is_simulation_enabled():
        return SimulatedGateway()

    target = provider or configured_provider()
    if target is None:
        raise PaymentGatewayUnavailableError(
            "SIMULATE_PAYMENT está en False pero no hay PAYMENT_PROVIDER "
            "configurado. Define el parámetro o vuelve a SIMULATE_PAYMENT=True.",
        )

    cls = get_gateway_class(target)
    if cls is None:
        raise PaymentGatewayUnavailableError(
            f"No hay adapter registrado para el proveedor '{target.value}'. "
            f"Probablemente falta instalar/registrar el módulo correspondiente.",
        )

    return cls()
