"""
Router por defecto: selección de proveedor para un cargo.

En FASE 0 la política es trivial — siempre devuelve el gateway que
resuelve la factory (simulator si ``SIMULATE_PAYMENT=True``; el provider
configurado en otro caso).

Esta clase queda lista para reemplazarse por reglas declarativas en una
futura iteración (ej. "país=CO + método=card → Wompi, fallback Stripe").
La firma pública es lo único que tiene que ser estable.
"""

from ...domain.interfaces import IPaymentGateway, IPaymentRouter
from ...domain.schemas import ChargeRequest
from ..gateways.factory import get_payment_gateway


class DefaultPaymentRouter(IPaymentRouter):
    """Router mínimo: delega 100% en la factory."""

    def select_gateway(self, request: ChargeRequest) -> IPaymentGateway:
        return get_payment_gateway()
