"""
State machine del ciclo de vida de un :class:`Charge`.

Define qué transiciones de estado son legales. Cualquier intento de
mover un Charge a un estado no permitido lanza
:class:`InvalidChargeTransitionError`.

Diagrama (resumido)::

    pending ─▶ processing ─▶ authorized ─▶ captured ─┬─▶ refunded
                │                │                    └─▶ partially_refunded ─▶ refunded
                │                ▼
                │           requires_action ─▶ authorized | captured | failed | canceled
                │
                ├─▶ failed
                └─▶ canceled

Notas:
  * El paso ``processing → captured`` es legal: muchos providers
    capturan en una sola llamada (auth+capture combinados).
  * Disputa puede surgir desde ``captured``, ``refunded`` o
    ``partially_refunded`` y vuelve a ``refunded`` si se pierde.
  * Estados terminales (sin salida posible): ``failed`` y ``canceled``.
"""

from .enums import ChargeStatus


class InvalidChargeTransitionError(Exception):
    """Se intentó una transición que la state machine no permite."""

    def __init__(self, current: ChargeStatus, target: ChargeStatus):
        self.current = current
        self.target = target
        super().__init__(
            f"Transición inválida del cargo: {current.value} → {target.value}",
        )


#: Mapa de transiciones legales.
TRANSITIONS: dict[ChargeStatus, set[ChargeStatus]] = {
    ChargeStatus.PENDING: {
        ChargeStatus.PROCESSING,
        ChargeStatus.REQUIRES_ACTION,
        ChargeStatus.AUTHORIZED,
        ChargeStatus.CAPTURED,
        ChargeStatus.FAILED,
        ChargeStatus.CANCELED,
    },
    ChargeStatus.PROCESSING: {
        ChargeStatus.REQUIRES_ACTION,
        ChargeStatus.AUTHORIZED,
        ChargeStatus.CAPTURED,
        ChargeStatus.FAILED,
        ChargeStatus.CANCELED,
    },
    ChargeStatus.REQUIRES_ACTION: {
        ChargeStatus.PROCESSING,
        ChargeStatus.AUTHORIZED,
        ChargeStatus.CAPTURED,
        ChargeStatus.FAILED,
        ChargeStatus.CANCELED,
    },
    ChargeStatus.AUTHORIZED: {
        ChargeStatus.CAPTURED,
        ChargeStatus.CANCELED,
        ChargeStatus.FAILED,
    },
    ChargeStatus.CAPTURED: {
        ChargeStatus.REFUNDED,
        ChargeStatus.PARTIALLY_REFUNDED,
        ChargeStatus.DISPUTED,
    },
    ChargeStatus.PARTIALLY_REFUNDED: {
        ChargeStatus.REFUNDED,
        ChargeStatus.DISPUTED,
    },
    ChargeStatus.REFUNDED: {
        ChargeStatus.DISPUTED,
    },
    ChargeStatus.DISPUTED: {
        ChargeStatus.REFUNDED,
        ChargeStatus.CAPTURED,
    },
    ChargeStatus.FAILED:   set(),
    ChargeStatus.CANCELED: set(),
}


def can_transition(current: ChargeStatus, target: ChargeStatus) -> bool:
    """Devuelve ``True`` si la transición es válida (idempotente incluida)."""
    if current == target:
        return True
    return target in TRANSITIONS.get(current, set())


def assert_transition(current: ChargeStatus, target: ChargeStatus) -> None:
    """Lanza :class:`InvalidChargeTransitionError` si la transición no es legal."""
    if not can_transition(current, target):
        raise InvalidChargeTransitionError(current, target)


def is_terminal(status: ChargeStatus) -> bool:
    """Estados sin salida posible."""
    return not TRANSITIONS.get(status, set())
