"""
Motor de escenarios del :class:`SimulatedGateway`.

Determina, a partir de la solicitud (``ChargeRequest``), qué respuesta
debe devolver el simulador. Reglas, en orden de prioridad:

1. **Override por metadata**: ``metadata['scenario'] = 'decline'`` (etc.)
2. **Tarjeta de prueba conocida** (mismo set que Stripe, para no
   reinventar): ``4000 0000 0000 0002`` ⇒ decline, etc.
3. **Por tipo de método**: card y wallet ⇒ succeed inmediato;
   PSE y voucher ⇒ async (``requires_action``).

Las decisiones son deterministas para que tests den siempre el mismo
resultado dado el mismo input.
"""

from enum import Enum
from typing import Optional

from ....domain.enums import MethodType
from ....domain.schemas import ChargeRequest


class Scenario(str, Enum):
    """Resultado simulado deseado para un cargo."""

    SUCCEED          = 'succeed'           # Captura inmediata
    AUTHORIZE_ONLY   = 'authorize_only'    # Auth sin capture
    REQUIRES_ACTION  = 'requires_action'   # 3DS / redirect
    ASYNC_PENDING    = 'async_pending'     # Espera webhook
    DECLINE          = 'decline'           # Falla rechazado
    INSUFFICIENT     = 'insufficient'      # Falla por fondos
    EXPIRED_CARD     = 'expired_card'      # Falla por tarjeta vencida
    PROCESSOR_ERROR  = 'processor_error'   # Falla genérica


#: Tarjetas de prueba reconocidas. Convención compatible con Stripe.
TEST_CARDS: dict[str, Scenario] = {
    '4242424242424242': Scenario.SUCCEED,
    '4000000000003220': Scenario.REQUIRES_ACTION,    # 3DS challenge
    '4000000000000002': Scenario.DECLINE,
    '4000000000009995': Scenario.INSUFFICIENT,
    '4000000000000069': Scenario.EXPIRED_CARD,
    '4000000000000119': Scenario.PROCESSOR_ERROR,
    '4111111111111111': Scenario.AUTHORIZE_ONLY,
}


_VALID_OVERRIDES = {s.value for s in Scenario}


def resolve_scenario(request: ChargeRequest) -> Scenario:
    """Devuelve el escenario que el simulator debe ejecutar."""

    override = _resolve_override(request)
    if override is not None:
        return override

    card_scenario = _resolve_by_card(request)
    if card_scenario is not None:
        return card_scenario

    return _resolve_by_method_type(request.method_type)


def _resolve_override(request: ChargeRequest) -> Optional[Scenario]:
    raw = request.metadata.get('scenario') if request.metadata else None
    if not raw:
        return None
    raw = str(raw).strip().lower()
    if raw not in _VALID_OVERRIDES:
        return None
    return Scenario(raw)


def _resolve_by_card(request: ChargeRequest) -> Optional[Scenario]:
    if request.method_type != MethodType.CARD or request.card is None:
        return None
    number = (request.card.number or '').replace(' ', '').replace('-', '')
    return TEST_CARDS.get(number)


def _resolve_by_method_type(method_type: MethodType) -> Scenario:
    # Por defecto los flujos asíncronos quedan en requires_action y
    # los síncronos en succeed. Esto refleja la realidad de PSE/voucher
    # (siempre exigen confirmación externa) vs tarjetas/wallets que
    # típicamente responden al instante.
    asynchronous = {MethodType.PSE, MethodType.VOUCHER, MethodType.BANK_TRANSFER}
    if method_type in asynchronous:
        return Scenario.ASYNC_PENDING
    return Scenario.SUCCEED
