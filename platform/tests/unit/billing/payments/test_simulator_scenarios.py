"""
Tests del motor de escenarios del simulator.

Estos no tocan el gateway en sí — verifican únicamente que
:func:`resolve_scenario` clasifica correctamente cada ``ChargeRequest``.
"""

import uuid
from decimal import Decimal

import pytest

from platform.features.billing.commerce.payments.domain.enums import MethodType
from platform.features.billing.commerce.payments.domain.schemas import (
    CardData,
    ChargeRequest,
    PayerRef,
)
from platform.features.billing.commerce.payments.infrastructure.gateways.simulator.scenarios import (
    Scenario,
    TEST_CARDS,
    resolve_scenario,
)


pytestmark = pytest.mark.unit


def _payer() -> PayerRef:
    return PayerRef(company_id=uuid.uuid4())


def _req(**overrides) -> ChargeRequest:
    defaults = dict(
        payer=_payer(),
        amount=Decimal('10000'),
        currency='COP',
        method_type=MethodType.CARD,
    )
    defaults.update(overrides)
    return ChargeRequest(**defaults)


# ── Override explícito por metadata ───────────────────────────────────────────


@pytest.mark.parametrize('scenario', list(Scenario))
def test_metadata_override_takes_highest_priority(scenario):
    """``metadata['scenario']='decline'`` siempre gana."""
    request = _req(
        metadata={'scenario': scenario.value},
        card=CardData(number='4242424242424242'),  # tarjeta que normalmente sería succeed
    )
    assert resolve_scenario(request) == scenario


def test_metadata_override_is_case_insensitive():
    request = _req(metadata={'scenario': 'DECLINE'})
    assert resolve_scenario(request) == Scenario.DECLINE


def test_metadata_override_with_unknown_value_falls_back():
    """Si el valor no es un escenario conocido, se ignora."""
    request = _req(
        metadata={'scenario': 'banana'},
        card=CardData(number='4242424242424242'),
    )
    assert resolve_scenario(request) == Scenario.SUCCEED  # fallback por tarjeta succeed


def test_metadata_override_with_empty_string_falls_back():
    request = _req(metadata={'scenario': ''})
    assert resolve_scenario(request) == Scenario.SUCCEED  # default por method_type=card


# ── Tarjetas de prueba reconocidas ────────────────────────────────────────────


@pytest.mark.parametrize('number,scenario', list(TEST_CARDS.items()))
def test_known_test_cards_map_to_expected_scenario(number, scenario):
    request = _req(card=CardData(number=number))
    assert resolve_scenario(request) == scenario


def test_test_card_works_with_spaces():
    request = _req(card=CardData(number='4242 4242 4242 4242'))
    assert resolve_scenario(request) == Scenario.SUCCEED


def test_test_card_works_with_dashes():
    request = _req(card=CardData(number='4000-0000-0000-0002'))
    assert resolve_scenario(request) == Scenario.DECLINE


def test_unknown_card_falls_back_to_default_for_card_method():
    request = _req(card=CardData(number='1234567890123456'))
    assert resolve_scenario(request) == Scenario.SUCCEED  # default para CARD


def test_card_lookup_skipped_when_method_is_not_card():
    """Tarjeta presente pero el método no es CARD ⇒ no se consulta la tabla."""
    request = _req(
        method_type=MethodType.PSE,
        card=CardData(number='4000000000000002'),  # normalmente decline
    )
    assert resolve_scenario(request) == Scenario.ASYNC_PENDING  # default para PSE


# ── Fallback por tipo de método ───────────────────────────────────────────────


@pytest.mark.parametrize('method_type', [
    MethodType.CARD,
    MethodType.WALLET,
    MethodType.BNPL,
    MethodType.CRYPTO,
    MethodType.OTHER,
])
def test_synchronous_methods_default_to_succeed(method_type):
    request = _req(method_type=method_type, card=None)
    assert resolve_scenario(request) == Scenario.SUCCEED


@pytest.mark.parametrize('method_type', [
    MethodType.PSE,
    MethodType.VOUCHER,
    MethodType.BANK_TRANSFER,
])
def test_asynchronous_methods_default_to_async_pending(method_type):
    request = _req(method_type=method_type, card=None)
    assert resolve_scenario(request) == Scenario.ASYNC_PENDING


# ── Determinismo ──────────────────────────────────────────────────────────────


def test_resolve_is_deterministic_for_same_input():
    request = _req(
        amount=Decimal('99.99'),
        card=CardData(number='4242424242424242'),
    )
    assert resolve_scenario(request) == resolve_scenario(request) == Scenario.SUCCEED
