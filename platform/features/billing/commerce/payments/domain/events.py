"""
Eventos de dominio del módulo de pagos + bus de publicación.

Otros bounded contexts (invoice, subscription, notificaciones, suspensión
de acceso en el cliente) reaccionan a *estos* eventos, nunca a webhooks
directos del provider. Esto mantiene base como única fuente de
verdad y desacopla integraciones futuras.

El bus es síncrono e in-process. Si en el futuro se quiere desacoplar
asíncronamente (Celery, NATS, etc.), se reemplaza la implementación de
:class:`_EventBus` sin tocar los publishers ni los handlers.

**Garantías**:
  * Los handlers se invocan en el orden en que se suscribieron.
  * Una excepción en un handler **NO** propaga al publisher ni afecta a
    los demás handlers: se registra con ``logging.exception``. Los
    eventos de pago no deben tumbar el flujo de cobro.
  * ``subscribe`` es idempotente: registrar el mismo handler dos veces
    se ignora silenciosamente.
"""

import logging
import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from .enums import ChargeStatus, GatewayProvider, MethodType


_logger = logging.getLogger('payments.events')


# ── Eventos ───────────────────────────────────────────────────────────────────


class PaymentDomainEvent(BaseModel):
    """Clase base de todos los eventos. Sirve para tipado y filtros."""

    charge_id: uuid.UUID
    company_id: uuid.UUID
    gateway_provider: GatewayProvider
    occurred_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class PaymentAuthorized(PaymentDomainEvent):
    amount: Decimal
    currency: str
    method_type: MethodType
    invoice_id: Optional[uuid.UUID] = None


class PaymentCaptured(PaymentDomainEvent):
    amount: Decimal
    currency: str
    method_type: MethodType
    invoice_id: Optional[uuid.UUID] = None


class PaymentFailed(PaymentDomainEvent):
    amount: Decimal
    currency: str
    method_type: MethodType
    failure_code: str = ''
    failure_message: str = ''
    invoice_id: Optional[uuid.UUID] = None


class PaymentCanceled(PaymentDomainEvent):
    reason: str = ''
    invoice_id: Optional[uuid.UUID] = None


class PaymentRequiresAction(PaymentDomainEvent):
    next_action_type: str
    next_action_url: str = ''


class PaymentRefunded(PaymentDomainEvent):
    refund_amount: Decimal
    total_refunded: Decimal
    is_partial: bool
    invoice_id: Optional[uuid.UUID] = None


class PaymentDisputed(PaymentDomainEvent):
    dispute_reason: str = ''
    invoice_id: Optional[uuid.UUID] = None


#: Conjunto de eventos finales (a efectos de cierre de cargo en flujos
#: dependientes). No equivalen 1:1 a estados terminales del Charge.
TERMINAL_EVENTS = {PaymentCaptured, PaymentFailed, PaymentCanceled, PaymentRefunded}


def event_for_status(status: ChargeStatus) -> Optional[type[PaymentDomainEvent]]:
    """
    Resuelve qué evento de dominio corresponde a una nueva transición de estado.

    Devuelve ``None`` si la transición no debe emitir evento
    (ej. ``pending → processing``, que es solo plomería interna).
    """

    mapping: dict[ChargeStatus, type[PaymentDomainEvent]] = {
        ChargeStatus.AUTHORIZED:         PaymentAuthorized,
        ChargeStatus.CAPTURED:           PaymentCaptured,
        ChargeStatus.FAILED:             PaymentFailed,
        ChargeStatus.CANCELED:           PaymentCanceled,
        ChargeStatus.REQUIRES_ACTION:    PaymentRequiresAction,
        ChargeStatus.REFUNDED:           PaymentRefunded,
        ChargeStatus.PARTIALLY_REFUNDED: PaymentRefunded,
        ChargeStatus.DISPUTED:           PaymentDisputed,
    }
    return mapping.get(status)


# ── Bus síncrono ──────────────────────────────────────────────────────────────


class _EventBus:
    """
    Pub/sub in-process. Una sola instancia (singleton de módulo).

    Los handlers son callables ``Callable[[PaymentDomainEvent], None]``.
    """

    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: type, handler: Callable) -> None:
        if handler in self._handlers.get(event_type, []):
            self._handlers[event_type].remove(handler)

    def publish(self, event: PaymentDomainEvent) -> None:
        for handler in list(self._handlers.get(type(event), [])):
            try:
                handler(event)
            except Exception:
                _logger.exception(
                    'payments event handler %r failed for %s',
                    handler, type(event).__name__,
                )

    def clear(self) -> None:
        """Limpia todos los handlers. Útil entre tests."""
        self._handlers.clear()

    def handler_count(self, event_type: type) -> int:
        """Cuenta handlers registrados para un evento. Útil para asserts en tests."""
        return len(self._handlers.get(event_type, []))


bus = _EventBus()

#: Aliases convenientes para no exponer la instancia.
subscribe = bus.subscribe
unsubscribe = bus.unsubscribe
publish = bus.publish
