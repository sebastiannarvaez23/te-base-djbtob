"""
:class:`SimulatedGateway` — implementación in-process de
:class:`IPaymentGateway` para SIMULATE_PAYMENT=True.

Sin red, sin estado en BD: mantiene un diccionario en memoria con los
cargos creados durante el proceso para soportar idempotencia y los
verbos confirm/capture/cancel/refund/fetch.

No pretende imitar a un proveedor concreto. Su objetivo es:
  * habilitar pruebas de facturación end-to-end sin infraestructura,
  * forzar caminos de fallo deterministas (vía scenarios),
  * verificar que la abstracción ``IPaymentGateway`` es realmente
    agnóstica del proveedor.

Las firmas de webhook se simulan con HMAC-SHA256 sobre el body usando
una clave fija (``SIMULATOR_WEBHOOK_SECRET``). En producción esto no
existe — es solo para que el endpoint de webhooks de FASE 2 tenga algo
con qué validar al recibir eventos del propio simulador.
"""

import hashlib
import hmac
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import Optional

from core.ids import uuid7

from ....domain.enums import (
    ChargeStatus,
    GatewayProvider,
    MethodType,
    NextActionType,
    WebhookEventType,
)
from ....domain.interfaces import IPaymentGateway
from ....domain.schemas import (
    ChargeRequest,
    ChargeResult,
    NextAction,
    RefundRequest,
    RefundResult,
    WebhookEvent,
)
from .scenarios import Scenario, resolve_scenario


SIMULATOR_WEBHOOK_SECRET = b'simulator-shared-secret'


# Errores canned por escenario.
_FAILURE_MAP: dict[Scenario, tuple[str, str]] = {
    Scenario.DECLINE:         ('card_declined',     'La tarjeta fue rechazada por el emisor.'),
    Scenario.INSUFFICIENT:    ('insufficient_funds', 'Fondos insuficientes en la cuenta.'),
    Scenario.EXPIRED_CARD:    ('expired_card',      'La tarjeta está vencida.'),
    Scenario.PROCESSOR_ERROR: ('processor_error',   'Error genérico del procesador.'),
}


@dataclass
class _StoredCharge:
    """Estado mínimo del cargo que el simulator mantiene en memoria."""

    gateway_charge_id: str
    status: ChargeStatus
    amount: Decimal
    currency: str
    method_type: MethodType
    failure_code: str = ''
    failure_message: str = ''
    refunded_amount: Decimal = Decimal('0')
    next_action: Optional[NextAction] = None
    metadata: dict = field(default_factory=dict)


class SimulatedGateway(IPaymentGateway):

    provider = GatewayProvider.SIMULATOR

    # Estado compartido entre instancias del proceso. El simulador no
    # persiste nada; cada arranque del proceso reinicia el "provider".
    _store: dict[str, _StoredCharge] = {}
    _idempotency: dict[str, ChargeResult] = {}
    _lock = threading.Lock()

    # ── create / confirm / capture / cancel ───────────────────────────

    def create_charge(self, request: ChargeRequest, idempotency_key: str) -> ChargeResult:
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency:
                return self._idempotency[idempotency_key]

            scenario = resolve_scenario(request)
            charge_id = self._mint_id('sim_ch')
            result = self._materialize(charge_id, request, scenario)

            self._store[charge_id] = _StoredCharge(
                gateway_charge_id=charge_id,
                status=result.status,
                amount=result.amount,
                currency=result.currency,
                method_type=result.method_type,
                failure_code=result.failure_code,
                failure_message=result.failure_message,
                next_action=result.next_action,
                metadata=dict(request.metadata or {}),
            )

            if idempotency_key:
                self._idempotency[idempotency_key] = result

            return result

    def confirm_charge(self, gateway_charge_id: str, payload: dict | None = None) -> ChargeResult:
        with self._lock:
            stored = self._require(gateway_charge_id)
            if stored.status == ChargeStatus.REQUIRES_ACTION:
                # Simula que el usuario completó 3DS / redirect.
                stored.status = ChargeStatus.CAPTURED
                stored.next_action = None
            elif stored.status == ChargeStatus.PROCESSING:
                stored.status = ChargeStatus.CAPTURED
                stored.next_action = None
            return self._snapshot(stored)

    def capture_charge(self, gateway_charge_id: str, amount: Optional[Decimal] = None) -> ChargeResult:
        with self._lock:
            stored = self._require(gateway_charge_id)
            if stored.status == ChargeStatus.AUTHORIZED:
                stored.status = ChargeStatus.CAPTURED
            return self._snapshot(stored)

    def cancel_charge(self, gateway_charge_id: str, reason: str = '') -> ChargeResult:
        with self._lock:
            stored = self._require(gateway_charge_id)
            if stored.status in {ChargeStatus.PENDING, ChargeStatus.PROCESSING,
                                 ChargeStatus.REQUIRES_ACTION, ChargeStatus.AUTHORIZED}:
                stored.status = ChargeStatus.CANCELED
                stored.next_action = None
            return self._snapshot(stored)

    # ── refunds ───────────────────────────────────────────────────────

    def refund_charge(self, request: RefundRequest) -> RefundResult:
        with self._lock:
            stored = self._require(request.gateway_charge_id)
            refund_amount = request.amount if request.amount is not None else (stored.amount - stored.refunded_amount)
            if refund_amount <= 0:
                return RefundResult(
                    gateway_provider=self.provider,
                    gateway_charge_id=stored.gateway_charge_id,
                    gateway_refund_id=self._mint_id('sim_rf'),
                    amount=Decimal('0'),
                    status=stored.status,
                    raw={'note': 'nothing to refund'},
                )

            stored.refunded_amount += refund_amount
            if stored.refunded_amount >= stored.amount:
                stored.status = ChargeStatus.REFUNDED
            else:
                stored.status = ChargeStatus.PARTIALLY_REFUNDED

            return RefundResult(
                gateway_provider=self.provider,
                gateway_charge_id=stored.gateway_charge_id,
                gateway_refund_id=self._mint_id('sim_rf'),
                amount=refund_amount,
                status=stored.status,
                raw={'reason': request.reason},
            )

    # ── reads ─────────────────────────────────────────────────────────

    def fetch_charge(self, gateway_charge_id: str) -> ChargeResult:
        with self._lock:
            stored = self._require(gateway_charge_id)
            return self._snapshot(stored)

    # ── webhooks ──────────────────────────────────────────────────────

    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        expected = hmac.new(SIMULATOR_WEBHOOK_SECRET, payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header or '')

    def parse_webhook_event(self, payload_bytes: bytes) -> WebhookEvent:
        data = json.loads(payload_bytes.decode('utf-8'))
        return WebhookEvent(
            provider=self.provider,
            external_event_id=str(data.get('id', uuid7())),
            event_type=WebhookEventType(data['type']),
            gateway_charge_id=str(data.get('charge_id', '')),
            status=ChargeStatus(data['status']) if 'status' in data else None,
            amount=Decimal(str(data['amount'])) if 'amount' in data else None,
            currency=data.get('currency', ''),
            occurred_at=datetime.now(dt_timezone.utc),
            raw=data,
        )

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _mint_id(prefix: str) -> str:
        return f"{prefix}_{uuid7().hex[:24]}"

    def _require(self, gateway_charge_id: str) -> _StoredCharge:
        if gateway_charge_id not in self._store:
            raise LookupError(f"Charge desconocido en simulator: {gateway_charge_id!r}")
        return self._store[gateway_charge_id]

    def _snapshot(self, stored: _StoredCharge) -> ChargeResult:
        return ChargeResult(
            gateway_provider=self.provider,
            gateway_charge_id=stored.gateway_charge_id,
            status=stored.status,
            amount=stored.amount,
            currency=stored.currency,
            method_type=stored.method_type,
            next_action=stored.next_action,
            failure_code=stored.failure_code,
            failure_message=stored.failure_message,
            raw={'simulator': True, 'metadata': stored.metadata},
        )

    def _materialize(self, charge_id: str, request: ChargeRequest, scenario: Scenario) -> ChargeResult:
        """Construye el ``ChargeResult`` inicial según el escenario."""

        base_kwargs = dict(
            gateway_provider=self.provider,
            gateway_charge_id=charge_id,
            amount=request.amount,
            currency=request.currency,
            method_type=request.method_type,
            raw={'simulator': True, 'scenario': scenario.value},
        )

        if scenario == Scenario.SUCCEED:
            return ChargeResult(status=ChargeStatus.CAPTURED, **base_kwargs)

        if scenario == Scenario.AUTHORIZE_ONLY:
            return ChargeResult(status=ChargeStatus.AUTHORIZED, **base_kwargs)

        if scenario == Scenario.REQUIRES_ACTION:
            next_action = NextAction(
                type=NextActionType.REDIRECT,
                url=request.return_url or 'https://simulator.local/3ds-challenge',
            )
            return ChargeResult(
                status=ChargeStatus.REQUIRES_ACTION,
                next_action=next_action,
                **base_kwargs,
            )

        if scenario == Scenario.ASYNC_PENDING:
            next_action = NextAction(
                type=NextActionType.AWAIT_WEBHOOK,
                voucher_reference=self._mint_id('sim_vch'),
            )
            return ChargeResult(
                status=ChargeStatus.PROCESSING,
                next_action=next_action,
                **base_kwargs,
            )

        # Escenarios de fallo.
        code, message = _FAILURE_MAP.get(scenario, ('unknown', 'Falla simulada.'))
        return ChargeResult(
            status=ChargeStatus.FAILED,
            failure_code=code,
            failure_message=message,
            **base_kwargs,
        )
