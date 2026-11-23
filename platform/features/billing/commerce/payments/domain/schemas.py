"""
Schemas Pydantic del dominio de pagos.

Contratos de entrada/salida que cruzan las capas (presentation →
application → infrastructure). Son *agnósticos del proveedor*: ningún
campo asume un proveedor concreto.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

from .enums import (
    AttemptOperation,
    AttemptResult,
    ChargeStatus,
    GatewayProvider,
    MethodType,
    NextActionType,
    WebhookEventType,
)


# ── Inputs hacia el gateway ────────────────────────────────────────────────────


class PayerRef(BaseModel):
    """
    Referencia mínima del pagador para el gateway.

    No incluimos el modelo Company completo para no acoplar a Django
    ni filtrar datos sensibles a los adapters.
    """

    company_id: uuid.UUID
    display_name: str = ''
    email: str = ''


class CardData(BaseModel):
    """
    Datos de tarjeta para flujos sin tokenización previa.

    En producción los providers reales reciben un token (Elements,
    Checkout, etc.). El simulator acepta este shape para permitir
    forzar escenarios por número de tarjeta.
    """

    number: str = ''
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    cvc: str = ''
    holder_name: str = ''


class ChargeRequest(BaseModel):
    """Solicitud para crear un nuevo cargo en el gateway."""

    payer: PayerRef
    amount: Decimal
    currency: str = ''
    method_type: MethodType = MethodType.CARD
    description: str = ''

    # Referencia opcional a un PaymentMethod ya tokenizado del lado del
    # provider. Si está presente, ``card`` se ignora.
    gateway_payment_method_id: str = ''

    # Solo para flujos sin tokenización previa (típicamente tests/simulador).
    card: Optional[CardData] = None

    # URLs de retorno para flujos asíncronos / 3DS.
    return_url: str = ''
    cancel_url: str = ''

    # Datos libres que el adapter puede pasar al provider.
    metadata: dict[str, Any] = Field(default_factory=dict)


class RefundRequest(BaseModel):
    gateway_charge_id: str
    amount: Optional[Decimal] = None   # None ⇒ reembolso total
    reason: str = ''
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Outputs del gateway ────────────────────────────────────────────────────────


class NextAction(BaseModel):
    type: NextActionType
    url: str = ''
    qr_data: str = ''
    voucher_reference: str = ''
    expires_at: Optional[datetime] = None


class ChargeResult(BaseModel):
    """
    Respuesta normalizada del gateway tras una operación sobre un cargo.

    Es lo que devuelven ``create_charge``, ``confirm_charge``,
    ``capture_charge``, ``cancel_charge`` y ``fetch_charge``.
    """

    gateway_provider: GatewayProvider
    gateway_charge_id: str
    status: ChargeStatus
    amount: Decimal
    currency: str = 'COP'
    method_type: MethodType
    next_action: Optional[NextAction] = None
    failure_code: str = ''
    failure_message: str = ''
    raw: dict[str, Any] = Field(default_factory=dict)


class RefundResult(BaseModel):
    gateway_provider: GatewayProvider
    gateway_charge_id: str
    gateway_refund_id: str
    amount: Decimal
    status: ChargeStatus
    raw: dict[str, Any] = Field(default_factory=dict)


# ── Webhooks ──────────────────────────────────────────────────────────────────


class WebhookEvent(BaseModel):
    """
    Evento de webhook normalizado.

    El WebhookTranslator del provider produce instancias de esta clase
    a partir del payload crudo. El ProcessWebhookUseCase trabaja
    exclusivamente con este shape.
    """

    provider: GatewayProvider
    external_event_id: str
    event_type: WebhookEventType
    gateway_charge_id: str = ''
    status: Optional[ChargeStatus] = None
    amount: Optional[Decimal] = None
    currency: str = ''
    occurred_at: Optional[datetime] = None
    raw: dict[str, Any] = Field(default_factory=dict)


# ── Persistencia del dominio (espejos del modelo Django) ──────────────────────


class ChargeAttemptSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    charge_id: uuid.UUID
    operation: AttemptOperation
    gateway_provider: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)
    result: AttemptResult
    error_message: str = ''
    attempted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ChargeSchema(BaseModel):
    id: Optional[uuid.UUID] = None
    idempotency_key: Optional[str] = None
    gateway_provider: str
    gateway_charge_id: str = ''

    company_id: uuid.UUID
    invoice_id: Optional[uuid.UUID] = None
    payment_method_id: Optional[uuid.UUID] = None
    company_subscription_id: Optional[uuid.UUID] = None

    amount: Decimal
    currency: str = 'COP'
    method_type: MethodType
    description: str = ''

    status: ChargeStatus
    next_action_type: str = ''
    next_action_url: str = ''
    failure_code: str = ''
    failure_message: str = ''

    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    refunded_amount: Decimal = Decimal('0')

    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreateChargeSchema(BaseModel):
    """Payload para persistir un Charge nuevo en BD."""

    idempotency_key: Optional[str] = None
    gateway_provider: str
    gateway_charge_id: str = ''
    company_id: uuid.UUID
    invoice_id: Optional[uuid.UUID] = None
    payment_method_id: Optional[uuid.UUID] = None
    company_subscription_id: Optional[uuid.UUID] = None
    amount: Decimal
    currency: str = 'COP'
    method_type: MethodType = MethodType.CARD
    description: str = ''
    status: ChargeStatus = ChargeStatus.PENDING
    next_action_type: str = ''
    next_action_url: str = ''
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateChargeStateSchema(BaseModel):
    """Transición de estado validada por la state machine."""

    status: ChargeStatus
    gateway_charge_id: Optional[str] = None
    next_action_type: str = ''
    next_action_url: str = ''
    failure_code: str = ''
    failure_message: str = ''
    authorized_at: Optional[datetime] = None
    captured_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    refunded_amount: Optional[Decimal] = None
    metadata: Optional[dict[str, Any]] = None


class WebhookInboxEntrySchema(BaseModel):
    id: Optional[uuid.UUID] = None
    provider: str
    external_event_id: str
    event_type: str = ''
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str = ''
    signature_verified: bool = False
    received_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    processing_error: str = ''
    charge_id: Optional[uuid.UUID] = None

    model_config = {"from_attributes": True}


class CreateWebhookInboxEntrySchema(BaseModel):
    provider: str
    external_event_id: str
    event_type: str = ''
    payload: dict[str, Any] = Field(default_factory=dict)
    signature: str = ''
    signature_verified: bool = False


class IdempotencyRecordSchema(BaseModel):
    key: str
    scope: str
    request_hash: str
    response_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    expires_at: datetime

    model_config = {"from_attributes": True}
