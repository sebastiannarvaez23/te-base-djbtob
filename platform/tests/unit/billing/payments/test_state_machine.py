"""
Tests de la state machine del Charge.

Comprueba que el grafo de transiciones legales coincide con la
documentación de :mod:`platform.features.billing.commerce.payments.domain.state_machine`
y que cualquier transición fuera de ese grafo se rechaza.
"""

import pytest

from platform.features.billing.commerce.payments.domain.enums import ChargeStatus
from platform.features.billing.commerce.payments.domain.state_machine import (
    InvalidChargeTransitionError,
    assert_transition,
    can_transition,
    is_terminal,
    TRANSITIONS,
)


pytestmark = pytest.mark.unit


# ── Transiciones legales documentadas ─────────────────────────────────────────


LEGAL_TRANSITIONS = [
    # Desde pending
    (ChargeStatus.PENDING, ChargeStatus.PROCESSING),
    (ChargeStatus.PENDING, ChargeStatus.REQUIRES_ACTION),
    (ChargeStatus.PENDING, ChargeStatus.AUTHORIZED),
    (ChargeStatus.PENDING, ChargeStatus.CAPTURED),
    (ChargeStatus.PENDING, ChargeStatus.FAILED),
    (ChargeStatus.PENDING, ChargeStatus.CANCELED),

    # Desde processing
    (ChargeStatus.PROCESSING, ChargeStatus.REQUIRES_ACTION),
    (ChargeStatus.PROCESSING, ChargeStatus.AUTHORIZED),
    (ChargeStatus.PROCESSING, ChargeStatus.CAPTURED),
    (ChargeStatus.PROCESSING, ChargeStatus.FAILED),
    (ChargeStatus.PROCESSING, ChargeStatus.CANCELED),

    # Desde requires_action
    (ChargeStatus.REQUIRES_ACTION, ChargeStatus.PROCESSING),
    (ChargeStatus.REQUIRES_ACTION, ChargeStatus.AUTHORIZED),
    (ChargeStatus.REQUIRES_ACTION, ChargeStatus.CAPTURED),
    (ChargeStatus.REQUIRES_ACTION, ChargeStatus.FAILED),
    (ChargeStatus.REQUIRES_ACTION, ChargeStatus.CANCELED),

    # Desde authorized
    (ChargeStatus.AUTHORIZED, ChargeStatus.CAPTURED),
    (ChargeStatus.AUTHORIZED, ChargeStatus.CANCELED),
    (ChargeStatus.AUTHORIZED, ChargeStatus.FAILED),

    # Desde captured
    (ChargeStatus.CAPTURED, ChargeStatus.REFUNDED),
    (ChargeStatus.CAPTURED, ChargeStatus.PARTIALLY_REFUNDED),
    (ChargeStatus.CAPTURED, ChargeStatus.DISPUTED),

    # Desde partially_refunded
    (ChargeStatus.PARTIALLY_REFUNDED, ChargeStatus.REFUNDED),
    (ChargeStatus.PARTIALLY_REFUNDED, ChargeStatus.DISPUTED),

    # Disputas pueden ir y volver
    (ChargeStatus.REFUNDED, ChargeStatus.DISPUTED),
    (ChargeStatus.DISPUTED, ChargeStatus.REFUNDED),
    (ChargeStatus.DISPUTED, ChargeStatus.CAPTURED),
]


# Algunas transiciones claramente ilegales (no necesita ser exhaustivo —
# la prueba "todas las no listadas son ilegales" lo cubre).
ILLEGAL_TRANSITIONS = [
    (ChargeStatus.FAILED, ChargeStatus.CAPTURED),
    (ChargeStatus.FAILED, ChargeStatus.PENDING),
    (ChargeStatus.CANCELED, ChargeStatus.CAPTURED),
    (ChargeStatus.CANCELED, ChargeStatus.AUTHORIZED),
    (ChargeStatus.PENDING, ChargeStatus.REFUNDED),
    (ChargeStatus.AUTHORIZED, ChargeStatus.REFUNDED),
    (ChargeStatus.CAPTURED, ChargeStatus.PENDING),
    (ChargeStatus.CAPTURED, ChargeStatus.PROCESSING),
    (ChargeStatus.REFUNDED, ChargeStatus.CAPTURED),
    (ChargeStatus.REFUNDED, ChargeStatus.PENDING),
]


@pytest.mark.parametrize('current,target', LEGAL_TRANSITIONS)
def test_legal_transitions_are_allowed(current, target):
    assert can_transition(current, target) is True
    assert_transition(current, target)  # no levanta


@pytest.mark.parametrize('current,target', ILLEGAL_TRANSITIONS)
def test_illegal_transitions_are_rejected(current, target):
    assert can_transition(current, target) is False
    with pytest.raises(InvalidChargeTransitionError):
        assert_transition(current, target)


# ── Idempotencia ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize('status', list(ChargeStatus))
def test_self_transition_is_always_idempotent(status):
    """Mover un cargo al mismo estado en el que está se considera válido."""
    assert can_transition(status, status) is True
    assert_transition(status, status)


# ── Estados terminales ────────────────────────────────────────────────────────


def test_failed_is_terminal():
    assert is_terminal(ChargeStatus.FAILED) is True


def test_canceled_is_terminal():
    assert is_terminal(ChargeStatus.CANCELED) is True


def test_captured_is_not_terminal_because_can_be_refunded():
    assert is_terminal(ChargeStatus.CAPTURED) is False


def test_refunded_is_not_terminal_because_can_be_disputed():
    assert is_terminal(ChargeStatus.REFUNDED) is False


# ── Cobertura exhaustiva del grafo ────────────────────────────────────────────


def test_every_status_is_present_in_the_transitions_map():
    """No queremos estados huérfanos en la state machine."""
    for status in ChargeStatus:
        assert status in TRANSITIONS, (
            f'Status {status.value} no está en TRANSITIONS — '
            f'puede dejar cargos atrapados.'
        )


def test_transitions_only_target_known_statuses():
    """Ningún destino apunta a un estado no definido."""
    valid = set(ChargeStatus)
    for source, targets in TRANSITIONS.items():
        for target in targets:
            assert target in valid, f'{source}→{target} apunta a estado desconocido'


def test_all_unlisted_pairs_are_illegal():
    """Cualquier (current, target) que no esté listado como legal o sea
    idempotente debe ser rechazado."""
    legal_set = set(LEGAL_TRANSITIONS)
    for current in ChargeStatus:
        for target in ChargeStatus:
            if current == target:
                continue
            if (current, target) in legal_set:
                continue
            assert not can_transition(current, target), (
                f'Transición {current}→{target} no está documentada como legal '
                f'pero la state machine la permite.'
            )


def test_invalid_transition_error_carries_context():
    """La excepción debe exponer el estado actual y el destino para diagnóstico."""
    with pytest.raises(InvalidChargeTransitionError) as exc_info:
        assert_transition(ChargeStatus.FAILED, ChargeStatus.CAPTURED)
    assert exc_info.value.current == ChargeStatus.FAILED
    assert exc_info.value.target == ChargeStatus.CAPTURED
