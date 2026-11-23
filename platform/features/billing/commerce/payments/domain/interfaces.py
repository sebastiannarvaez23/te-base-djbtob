"""
Puertos del dominio de pagos.

El dominio depende de estas interfaces; los adapters (Stripe, Wompi,
sandbox, simulator) implementan ``IPaymentGateway``. Los repositorios
Django implementan ``IChargeRepository``, ``IWebhookInboxRepository`` e
``IIdempotencyStore``.

Regla dura: nada de tipos de un provider concreto en estas firmas.
Todo entra/sale como :mod:`.schemas`.
"""

import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional

from core.query.core import PaginatedQuery, PaginatedResult

from .enums import GatewayProvider
from .schemas import (
    ChargeAttemptSchema,
    ChargeRequest,
    ChargeResult,
    ChargeSchema,
    CreateChargeSchema,
    CreateWebhookInboxEntrySchema,
    IdempotencyRecordSchema,
    RefundRequest,
    RefundResult,
    UpdateChargeStateSchema,
    WebhookEvent,
    WebhookInboxEntrySchema,
)


# ── Puerto del proveedor ──────────────────────────────────────────────────────


class IPaymentGateway(ABC):
    """
    Contrato que todo adapter de proveedor debe cumplir.

    Implementaciones esperadas (en FASE 1 solo el simulator):
      * :class:`...gateways.simulator.SimulatedGateway`
      * StripeGateway, WompiGateway, etc. (FASE 5)

    Cada método representa una operación atómica del proveedor. El
    estado en BD lo gestiona el use case que orquesta la llamada, no
    el adapter. El adapter solo traduce.
    """

    #: Identificador del adapter; debe coincidir con ``GatewayProvider``.
    provider: GatewayProvider

    @abstractmethod
    def create_charge(self, request: ChargeRequest, idempotency_key: str) -> ChargeResult:
        """Crea un cargo en el provider. Idempotente vía ``idempotency_key``."""
        ...

    @abstractmethod
    def confirm_charge(self, gateway_charge_id: str, payload: dict | None = None) -> ChargeResult:
        """Confirma un cargo que estaba en ``requires_action`` o ``processing``."""
        ...

    @abstractmethod
    def capture_charge(self, gateway_charge_id: str, amount: Optional[Decimal] = None) -> ChargeResult:
        """Captura un cargo previamente autorizado. ``amount=None`` ⇒ monto completo."""
        ...

    @abstractmethod
    def cancel_charge(self, gateway_charge_id: str, reason: str = '') -> ChargeResult:
        """Cancela un cargo no capturado todavía."""
        ...

    @abstractmethod
    def refund_charge(self, request: RefundRequest) -> RefundResult:
        """Reembolsa un cargo capturado. Soporta reembolsos parciales."""
        ...

    @abstractmethod
    def fetch_charge(self, gateway_charge_id: str) -> ChargeResult:
        """Consulta el estado actual del cargo (para reconciliación)."""
        ...

    @abstractmethod
    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        """Valida la firma del webhook entrante. ``True`` si es legítimo."""
        ...

    @abstractmethod
    def parse_webhook_event(self, payload_bytes: bytes) -> WebhookEvent:
        """Traduce un payload crudo al evento normalizado del dominio."""
        ...


# ── Selección de gateway ──────────────────────────────────────────────────────


class IPaymentRouter(ABC):
    """
    Política de selección de proveedor para un cargo dado.

    Permite reglas tipo "Colombia + tarjeta → Wompi", "PSE → solo Wompi",
    fallback chains, etc. La implementación por defecto (FASE 0) solo
    delega en la factory + parámetro ``PAYMENT_PROVIDER``.
    """

    @abstractmethod
    def select_gateway(self, request: ChargeRequest) -> IPaymentGateway:
        ...


# ── Webhook translation ───────────────────────────────────────────────────────


class IWebhookTranslator(ABC):
    """
    Traductor de webhooks específico de un provider.

    Cada provider tiene su propio formato (Stripe, Wompi, PayU, ...);
    el adapter expone también una implementación de esta interfaz para
    convertir payloads crudos a :class:`WebhookEvent`.

    En el flujo normal, ``IPaymentGateway.parse_webhook_event`` suele
    delegar en una implementación de esta interfaz.
    """

    provider: GatewayProvider

    @abstractmethod
    def verify_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        ...

    @abstractmethod
    def translate(self, payload_bytes: bytes) -> WebhookEvent:
        ...


# ── Persistencia ──────────────────────────────────────────────────────────────


class IChargeRepository(ABC):

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> Optional[ChargeSchema]:
        ...

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> Optional[ChargeSchema]:
        ...

    @abstractmethod
    def get_by_gateway_ref(self, provider: str, gateway_charge_id: str) -> Optional[ChargeSchema]:
        ...

    @abstractmethod
    def list_by_company(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult:
        ...

    @abstractmethod
    def create(self, data: CreateChargeSchema) -> ChargeSchema:
        ...

    @abstractmethod
    def transition(self, id: uuid.UUID, data: UpdateChargeStateSchema) -> Optional[ChargeSchema]:
        """
        Aplica una transición de estado validada por la state machine.

        Implementaciones deben usar ``select_for_update`` u otra estrategia
        de concurrencia para evitar transiciones en paralelo.
        """
        ...

    @abstractmethod
    def add_attempt(self, attempt: ChargeAttemptSchema) -> ChargeAttemptSchema:
        ...

    @abstractmethod
    def bind_period(self, charge_id: uuid.UUID, period_id: uuid.UUID) -> Optional[ChargeSchema]:
        """Stamp ``company_subscription_id`` on the charge. None if missing."""
        ...


class IWebhookInboxRepository(ABC):

    @abstractmethod
    def get_by_external_id(self, provider: str, external_event_id: str) -> Optional[WebhookInboxEntrySchema]:
        ...

    @abstractmethod
    def create(self, data: CreateWebhookInboxEntrySchema) -> WebhookInboxEntrySchema:
        ...

    @abstractmethod
    def mark_processed(
        self,
        id: uuid.UUID,
        charge_id: Optional[uuid.UUID] = None,
        error: str = '',
    ) -> Optional[WebhookInboxEntrySchema]:
        ...

    @abstractmethod
    def list_unprocessed(self, limit: int = 100) -> List[WebhookInboxEntrySchema]:
        ...


class IIdempotencyStore(ABC):

    @abstractmethod
    def get(self, scope: str, key: str) -> Optional[IdempotencyRecordSchema]:
        ...

    @abstractmethod
    def put(
        self,
        scope: str,
        key: str,
        request_hash: str,
        response_payload: dict,
        ttl_seconds: int = 24 * 60 * 60,
    ) -> IdempotencyRecordSchema:
        ...

    @abstractmethod
    def purge_expired(self) -> int:
        ...


class ICountryCurrencyPolicy(ABC):
    """Validates charge currency against the company country catalog."""

    @abstractmethod
    def assert_charge_currency(self, *, company_id: uuid.UUID, currency: str) -> str:
        """Normalize and assert ``currency`` is allowed. Returns uppercase code."""
        ...

    @abstractmethod
    def default_currency_for_company(self, company_id: uuid.UUID) -> str:
        """Country default currency, or platform fallback when geo/links missing."""
        ...

    @abstractmethod
    def assert_refund_currency(self, *, charge_currency: str, currency: str) -> str:
        """Ensure refund currency matches the charge. Returns uppercase code."""
        ...
