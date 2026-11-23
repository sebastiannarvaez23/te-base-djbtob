"""
core/realtime/
──────────────
Infraestructura transversal de tiempo real (WebSockets sobre Django Channels).

Igual que ``core.audit`` o ``core.errors``, este paquete es cross-cutting:
cualquier feature puede emitir mensajes en vivo sin conocer los detalles de
Channels, usando el puerto ``IRealtimePublisher`` desde código síncrono, o
construir un consumidor declarando solo sus grupos sobre ``BaseRealtimeConsumer``.

Piezas:
  - envelope.py   → RealtimeMessage: contrato estándar del payload.
  - groups.py     → RealtimeGroups: nombres de grupo namespaced por tenant.
  - publisher.py  → IRealtimePublisher (+ impl Channels y factory): SALIDA.
  - consumers.py  → BaseRealtimeConsumer: ENTRADA (cliente → servidor).
  - auth.py       → JWTAuthMiddleware: resuelve el usuario desde la cookie JWT.
  - tenant.py     → TenantContextMiddleware: resuelve el schema del usuario.
"""

from core.realtime.envelope import RealtimeMessage
from core.realtime.groups import RealtimeGroups
from core.realtime.publisher import IRealtimePublisher, RealtimePublisherFactory

__all__ = [
    'RealtimeMessage',
    'RealtimeGroups',
    'IRealtimePublisher',
    'RealtimePublisherFactory',
]
