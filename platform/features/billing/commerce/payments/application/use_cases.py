"""
Use cases del módulo de pagos.

Cada use case representa **una sola** intención de negocio. Reciben sus
dependencias (repositorio, router de gateway) por constructor y exponen
``execute(...)``. Validan invariantes, orquestan el adapter del provider
y aplican transiciones contra la state machine — pero no conocen ni el
provider concreto ni el ORM.

Ningún use case importa ``models`` directamente: solo trabaja con
schemas Pydantic e interfaces de :mod:`...domain`.
"""

import uuid
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from typing import List, Optional

from core.errors import AppErrorCode, AppException, ConflictException, NotFoundException, ServerException
from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.enums import AttemptOperation, AttemptResult, ChargeStatus, GatewayProvider
from ..domain.events import (
    PaymentAuthorized,
    PaymentCanceled,
    PaymentCaptured,
    PaymentDisputed,
    PaymentDomainEvent,
    PaymentFailed,
    PaymentRefunded,
    PaymentRequiresAction,
    event_for_status,
    publish,
)
from ..domain.interfaces import (
    IChargeRepository,
    ICountryCurrencyPolicy,
    IPaymentRouter,
    IWebhookInboxRepository,
)
from ..domain.schemas import (
    ChargeAttemptSchema,
    ChargeRequest,
    ChargeResult,
    ChargeSchema,
    CreateChargeSchema,
    RefundRequest,
    RefundResult,
    UpdateChargeStateSchema,
    WebhookEvent,
    WebhookInboxEntrySchema,
)
from ..domain.state_machine import InvalidChargeTransitionError
from core.trace import trace_layer


# ── Helpers internos ──────────────────────────────────────────────────────────


def _persist_state(
    repo: IChargeRepository,
    charge_id: uuid.UUID,
    result: ChargeResult,
    *,
    previous_status: ChargeStatus,
    refunded_amount: Optional[Decimal] = None,
    previous_refunded: Optional[Decimal] = None,
) -> ChargeSchema:
    """
    Aplica el ``ChargeResult`` devuelto por el gateway sobre el Charge en BD.

    Convierte el shape del puerto a un ``UpdateChargeStateSchema`` y lo
    pasa por la state machine vía el repositorio. Si la transición
    cambia de estado, publica el evento de dominio correspondiente en
    el :mod:`...domain.events` bus.

    ``previous_status`` lo pasa el caller (que ya cargó el charge) para
    no incurrir en otro round-trip de BD y para que la decisión de
    publicar evento sea explícita.
    """
    now = datetime.now(dt_timezone.utc)
    update_kwargs = dict(
        status=result.status,
        gateway_charge_id=result.gateway_charge_id or None,
        failure_code=result.failure_code,
        failure_message=result.failure_message,
    )
    if result.next_action is not None:
        update_kwargs['next_action_type'] = result.next_action.type.value
        update_kwargs['next_action_url'] = result.next_action.url

    if result.status == ChargeStatus.AUTHORIZED:
        update_kwargs['authorized_at'] = now
    if result.status == ChargeStatus.CAPTURED:
        update_kwargs['captured_at'] = now
    if result.status == ChargeStatus.CANCELED:
        update_kwargs['canceled_at'] = now
    if refunded_amount is not None:
        update_kwargs['refunded_amount'] = refunded_amount

    try:
        updated = repo.transition(charge_id, UpdateChargeStateSchema(**update_kwargs))
    except InvalidChargeTransitionError as exc:
        raise ConflictException(
            AppErrorCode.PAY_INVALID_TRANSITION,
            override_detail=str(exc),
            context={'charge_id': str(charge_id), 'target': result.status.value},
        )

    if updated is None:
        raise NotFoundException(AppErrorCode.PAY_CHARGE_NOT_FOUND)

    # Publicamos evento sólo si el estado cambió de verdad. Esto evita
    # ruido por reintentos / webhooks duplicados que confirman lo mismo.
    if updated.status != previous_status:
        event = _build_event(updated, previous_refunded=previous_refunded)
        if event is not None:
            publish(event)

    return updated


def _build_event(
    charge: ChargeSchema,
    *,
    previous_refunded: Optional[Decimal] = None,
) -> Optional[PaymentDomainEvent]:
    """Construye el evento de dominio que corresponde al estado actual del cargo."""

    event_cls = event_for_status(charge.status)
    if event_cls is None:
        return None

    try:
        provider = GatewayProvider(charge.gateway_provider)
    except ValueError:
        # Provider desconocido: no publicamos para no propagar basura.
        return None

    base = dict(
        charge_id=charge.id,
        company_id=charge.company_id,
        gateway_provider=provider,
        occurred_at=datetime.now(dt_timezone.utc),
        metadata=dict(charge.metadata or {}),
    )

    if event_cls is PaymentCaptured:
        return PaymentCaptured(
            **base,
            amount=charge.amount,
            currency=charge.currency,
            method_type=charge.method_type,
            invoice_id=charge.invoice_id,
        )
    if event_cls is PaymentAuthorized:
        return PaymentAuthorized(
            **base,
            amount=charge.amount,
            currency=charge.currency,
            method_type=charge.method_type,
            invoice_id=charge.invoice_id,
        )
    if event_cls is PaymentFailed:
        return PaymentFailed(
            **base,
            amount=charge.amount,
            currency=charge.currency,
            method_type=charge.method_type,
            failure_code=charge.failure_code,
            failure_message=charge.failure_message,
            invoice_id=charge.invoice_id,
        )
    if event_cls is PaymentCanceled:
        return PaymentCanceled(**base, invoice_id=charge.invoice_id)
    if event_cls is PaymentRequiresAction:
        return PaymentRequiresAction(
            **base,
            next_action_type=charge.next_action_type,
            next_action_url=charge.next_action_url,
        )
    if event_cls is PaymentRefunded:
        is_partial = charge.status == ChargeStatus.PARTIALLY_REFUNDED
        refund_amount = charge.refunded_amount - (previous_refunded or Decimal('0'))
        return PaymentRefunded(
            **base,
            refund_amount=refund_amount,
            total_refunded=charge.refunded_amount,
            is_partial=is_partial,
            invoice_id=charge.invoice_id,
        )
    if event_cls is PaymentDisputed:
        return PaymentDisputed(**base, invoice_id=charge.invoice_id)
    return None


def _record_attempt(
    repo: IChargeRepository,
    charge_id: uuid.UUID,
    operation: AttemptOperation,
    gateway_provider: str,
    request_payload: dict,
    response_payload: dict,
    result: AttemptResult,
    error_message: str = '',
) -> None:
    repo.add_attempt(ChargeAttemptSchema(
        charge_id=charge_id,
        operation=operation,
        gateway_provider=gateway_provider,
        request_payload=request_payload,
        response_payload=response_payload,
        result=result,
        error_message=error_message,
    ))


def _result_to_attempt_status(status: ChargeStatus) -> AttemptResult:
    if status in (ChargeStatus.FAILED, ChargeStatus.CANCELED):
        return AttemptResult.FAILED
    if status in (ChargeStatus.PENDING, ChargeStatus.PROCESSING, ChargeStatus.REQUIRES_ACTION):
        return AttemptResult.PENDING
    return AttemptResult.SUCCEEDED


# ── Lecturas ──────────────────────────────────────────────────────────────────


class GetChargeByIdUseCase:

    def __init__(self, repository: IChargeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, charge_id: uuid.UUID) -> ChargeSchema:
        charge = self.repository.get_by_id(charge_id)
        if charge is None:
            raise NotFoundException(AppErrorCode.PAY_CHARGE_NOT_FOUND)
        return charge


class GetChargesByCompanyUseCase:

    def __init__(self, repository: IChargeRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.list_by_company(company_id, query)


# ── Escritura: create ─────────────────────────────────────────────────────────


class CreateChargeUseCase:
    """
    Crea un cargo en BD y lo envía al gateway.

    Flujo:
      1. Si ``idempotency_key`` ya existe en BD ⇒ devolvemos el cargo
         existente (safe retry desde el cliente).
      2. Validamos moneda contra el catálogo país→monedas (fail-fast).
      3. Persistimos el Charge en estado ``pending``.
      4. Invocamos ``gateway.create_charge``.
      5. Registramos el ``ChargeAttempt`` con el resultado.
      6. Aplicamos la transición de estado vía la state machine.
      7. Devolvemos el ``ChargeSchema`` actualizado.

    Si el gateway lanza una excepción, registramos el intento como
    fallido y propagamos un :class:`ServerException` con ``PAY_007``.
    """

    def __init__(
        self,
        repository: IChargeRepository,
        router: IPaymentRouter,
        currency_policy: ICountryCurrencyPolicy,
        period_lookup=None,
    ):
        self.repository = repository
        self.router = router
        self._currency_policy = currency_policy
        self._period_lookup = period_lookup

    @trace_layer('application')
    def execute(
        self,
        request: ChargeRequest,
        company_id: uuid.UUID,
        idempotency_key: Optional[str] = None,
        invoice_id: Optional[uuid.UUID] = None,
        payment_method_id: Optional[uuid.UUID] = None,
    ) -> ChargeSchema:

        if idempotency_key:
            existing = self.repository.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                return existing

        policy = self._currency_policy
        currency = policy.assert_charge_currency(
            company_id=company_id,
            currency=request.currency or '',
        )
        request = request.model_copy(update={'currency': currency})

        gateway = self.router.select_gateway(request)
        provider = gateway.provider.value

        period_id = None
        try:
            lookup = self._period_lookup
            if lookup is None:
                from platform.features.billing.subscription.subscription.infrastructure.active_period import (
                    DjangoActivePeriodLookup,
                )
                lookup = DjangoActivePeriodLookup()
            period = lookup.get(company_id)
            if period is not None:
                period_id = period.id
        except Exception:
            period_id = None

        created = self.repository.create(CreateChargeSchema(
            idempotency_key=idempotency_key,
            gateway_provider=provider,
            company_id=company_id,
            invoice_id=invoice_id,
            payment_method_id=payment_method_id,
            company_subscription_id=period_id,
            amount=request.amount,
            currency=currency,
            method_type=request.method_type,
            description=request.description,
            metadata=dict(request.metadata or {}),
        ))

        try:
            result = gateway.create_charge(request, idempotency_key or '')
        except Exception as exc:
            _record_attempt(
                self.repository, created.id, AttemptOperation.CREATE, provider,
                request_payload=request.model_dump(mode='json'),
                response_payload={},
                result=AttemptResult.FAILED,
                error_message=str(exc)[:512],
            )
            raise ServerException(
                AppErrorCode.PAY_PROVIDER_ERROR,
                override_detail=f"Payment provider '{provider}' communication failed: {exc}",
            )

        _record_attempt(
            self.repository, created.id, AttemptOperation.CREATE, provider,
            request_payload=request.model_dump(mode='json'),
            response_payload=result.model_dump(mode='json'),
            result=_result_to_attempt_status(result.status),
        )

        return _persist_state(
            self.repository, created.id, result,
            previous_status=created.status,
        )


# ── Escritura: confirm / capture / cancel ─────────────────────────────────────


class ConfirmChargeUseCase:
    """Confirma un cargo que estaba en ``requires_action`` o ``processing``."""

    def __init__(self, repository: IChargeRepository, router: IPaymentRouter):
        self.repository = repository
        self.router = router

    @trace_layer('application')
    def execute(self, charge_id: uuid.UUID, payload: Optional[dict] = None) -> ChargeSchema:
        charge = self._load(charge_id)
        gateway = self.router.select_gateway(self._stub_request(charge))
        try:
            result = gateway.confirm_charge(charge.gateway_charge_id, payload)
        except Exception as exc:
            _record_attempt(
                self.repository, charge.id, AttemptOperation.CONFIRM, charge.gateway_provider,
                request_payload={'payload': payload or {}}, response_payload={},
                result=AttemptResult.FAILED, error_message=str(exc)[:512],
            )
            raise ServerException(AppErrorCode.PAY_PROVIDER_ERROR, override_detail=str(exc))

        _record_attempt(
            self.repository, charge.id, AttemptOperation.CONFIRM, charge.gateway_provider,
            request_payload={'payload': payload or {}},
            response_payload=result.model_dump(mode='json'),
            result=_result_to_attempt_status(result.status),
        )
        return _persist_state(
            self.repository, charge.id, result,
            previous_status=charge.status,
        )

    def _load(self, charge_id: uuid.UUID) -> ChargeSchema:
        charge = self.repository.get_by_id(charge_id)
        if charge is None:
            raise NotFoundException(AppErrorCode.PAY_CHARGE_NOT_FOUND)
        return charge

    @staticmethod
    def _stub_request(charge: ChargeSchema) -> ChargeRequest:
        """Reconstruye un ChargeRequest mínimo para que el router pueda elegir gateway.

        En FASE 0/1 el router solo mira la factory, así que basta con
        un shape válido. Si en el futuro las políticas miran el método
        o moneda, aquí ya hay con qué.
        """
        from ..domain.schemas import PayerRef
        return ChargeRequest(
            payer=PayerRef(company_id=charge.company_id),
            amount=charge.amount,
            currency=charge.currency,
            method_type=charge.method_type,
        )


class CaptureChargeUseCase:
    """Captura un cargo previamente autorizado."""

    def __init__(self, repository: IChargeRepository, router: IPaymentRouter):
        self.repository = repository
        self.router = router

    @trace_layer('application')
    def execute(self, charge_id: uuid.UUID, amount: Optional[Decimal] = None) -> ChargeSchema:
        charge = self._load(charge_id)
        gateway = self.router.select_gateway(ConfirmChargeUseCase._stub_request(charge))
        try:
            result = gateway.capture_charge(charge.gateway_charge_id, amount)
        except Exception as exc:
            _record_attempt(
                self.repository, charge.id, AttemptOperation.CAPTURE, charge.gateway_provider,
                request_payload={'amount': str(amount) if amount else None},
                response_payload={}, result=AttemptResult.FAILED,
                error_message=str(exc)[:512],
            )
            raise ServerException(AppErrorCode.PAY_PROVIDER_ERROR, override_detail=str(exc))

        _record_attempt(
            self.repository, charge.id, AttemptOperation.CAPTURE, charge.gateway_provider,
            request_payload={'amount': str(amount) if amount else None},
            response_payload=result.model_dump(mode='json'),
            result=_result_to_attempt_status(result.status),
        )
        return _persist_state(
            self.repository, charge.id, result,
            previous_status=charge.status,
        )

    def _load(self, charge_id: uuid.UUID) -> ChargeSchema:
        charge = self.repository.get_by_id(charge_id)
        if charge is None:
            raise NotFoundException(AppErrorCode.PAY_CHARGE_NOT_FOUND)
        return charge


class CancelChargeUseCase:

    def __init__(self, repository: IChargeRepository, router: IPaymentRouter):
        self.repository = repository
        self.router = router

    @trace_layer('application')
    def execute(self, charge_id: uuid.UUID, reason: str = '') -> ChargeSchema:
        charge = self.repository.get_by_id(charge_id)
        if charge is None:
            raise NotFoundException(AppErrorCode.PAY_CHARGE_NOT_FOUND)
        gateway = self.router.select_gateway(ConfirmChargeUseCase._stub_request(charge))
        try:
            result = gateway.cancel_charge(charge.gateway_charge_id, reason)
        except Exception as exc:
            _record_attempt(
                self.repository, charge.id, AttemptOperation.CANCEL, charge.gateway_provider,
                request_payload={'reason': reason}, response_payload={},
                result=AttemptResult.FAILED, error_message=str(exc)[:512],
            )
            raise ServerException(AppErrorCode.PAY_PROVIDER_ERROR, override_detail=str(exc))

        _record_attempt(
            self.repository, charge.id, AttemptOperation.CANCEL, charge.gateway_provider,
            request_payload={'reason': reason},
            response_payload=result.model_dump(mode='json'),
            result=_result_to_attempt_status(result.status),
        )
        return _persist_state(
            self.repository, charge.id, result,
            previous_status=charge.status,
        )


# ── Escritura: refund ─────────────────────────────────────────────────────────


class RefundChargeUseCase:
    """Emite un reembolso (parcial o total) sobre un cargo capturado."""

    def __init__(
        self,
        repository: IChargeRepository,
        router: IPaymentRouter,
        currency_policy: ICountryCurrencyPolicy,
    ):
        self.repository = repository
        self.router = router
        self._currency_policy = currency_policy

    @trace_layer('application')
    def execute(
        self,
        charge_id: uuid.UUID,
        amount: Optional[Decimal] = None,
        reason: str = '',
        currency: Optional[str] = None,
    ) -> ChargeSchema:
        charge = self.repository.get_by_id(charge_id)
        if charge is None:
            raise NotFoundException(AppErrorCode.PAY_CHARGE_NOT_FOUND)

        self._currency_policy.assert_refund_currency(
            charge_currency=charge.currency,
            currency=currency if currency is not None else charge.currency,
        )

        gateway = self.router.select_gateway(ConfirmChargeUseCase._stub_request(charge))
        try:
            refund_result: RefundResult = gateway.refund_charge(RefundRequest(
                gateway_charge_id=charge.gateway_charge_id,
                amount=amount,
                reason=reason,
            ))
        except Exception as exc:
            _record_attempt(
                self.repository, charge.id, AttemptOperation.REFUND, charge.gateway_provider,
                request_payload={'amount': str(amount) if amount else None, 'reason': reason},
                response_payload={}, result=AttemptResult.FAILED,
                error_message=str(exc)[:512],
            )
            raise ServerException(AppErrorCode.PAY_PROVIDER_ERROR, override_detail=str(exc))

        _record_attempt(
            self.repository, charge.id, AttemptOperation.REFUND, charge.gateway_provider,
            request_payload={'amount': str(amount) if amount else None, 'reason': reason},
            response_payload=refund_result.model_dump(mode='json'),
            result=_result_to_attempt_status(refund_result.status),
        )

        # Construye un ChargeResult artificial para reusar _persist_state.
        new_refunded = charge.refunded_amount + refund_result.amount
        synthetic = ChargeResult(
            gateway_provider=gateway.provider,
            gateway_charge_id=charge.gateway_charge_id,
            status=refund_result.status,
            amount=charge.amount,
            currency=charge.currency,
            method_type=charge.method_type,
        )
        return _persist_state(
            self.repository, charge.id, synthetic,
            previous_status=charge.status,
            refunded_amount=new_refunded,
            previous_refunded=charge.refunded_amount,
        )


# ── Lectura desde provider: fetch (reconciliation) ────────────────────────────


class FetchChargeUseCase:
    """Consulta el provider y reconcilia el estado local."""

    def __init__(self, repository: IChargeRepository, router: IPaymentRouter):
        self.repository = repository
        self.router = router

    @trace_layer('application')
    def execute(self, charge_id: uuid.UUID) -> ChargeSchema:
        charge = self.repository.get_by_id(charge_id)
        if charge is None:
            raise NotFoundException(AppErrorCode.PAY_CHARGE_NOT_FOUND)
        gateway = self.router.select_gateway(ConfirmChargeUseCase._stub_request(charge))
        try:
            result = gateway.fetch_charge(charge.gateway_charge_id)
        except Exception as exc:
            _record_attempt(
                self.repository, charge.id, AttemptOperation.FETCH, charge.gateway_provider,
                request_payload={}, response_payload={},
                result=AttemptResult.FAILED, error_message=str(exc)[:512],
            )
            raise ServerException(AppErrorCode.PAY_PROVIDER_ERROR, override_detail=str(exc))

        _record_attempt(
            self.repository, charge.id, AttemptOperation.FETCH, charge.gateway_provider,
            request_payload={}, response_payload=result.model_dump(mode='json'),
            result=_result_to_attempt_status(result.status),
        )
        # Si el provider está exactamente en el mismo estado, no aplicamos
        # transición (sería idempotente, pero evitamos updated_at falso).
        if result.status == charge.status:
            return charge
        try:
            return _persist_state(
                self.repository, charge.id, result,
                previous_status=charge.status,
            )
        except ConflictException:
            # Reconciliación contra estado terminal: lo dejamos como está.
            return charge


# ── Webhooks ──────────────────────────────────────────────────────────────────


class ProcessWebhookUseCase:
    """
    Procesa un evento de webhook ya almacenado en la inbox.

    Se ejecuta de forma asíncrona (worker) o sincrónica tras
    almacenar el payload. Aplica la transición de estado sobre el
    Charge referenciado, vía la state machine.
    """

    def __init__(
        self,
        charge_repo: IChargeRepository,
        inbox_repo: IWebhookInboxRepository,
        router: IPaymentRouter,
    ):
        self.charge_repo = charge_repo
        self.inbox_repo = inbox_repo
        self.router = router

    @trace_layer('application')
    def execute(self, entry: WebhookInboxEntrySchema) -> Optional[ChargeSchema]:
        if entry.id is None:
            raise ServerException(
                AppErrorCode.SERVER_ERROR,
                override_detail='WebhookInboxEntry without id cannot be processed.',
            )

        # Si la entrada no fue verificada o ya está procesada, rechazamos.
        if not entry.signature_verified:
            self.inbox_repo.mark_processed(entry.id, error='signature not verified')
            raise AppException(AppErrorCode.PAY_WEBHOOK_INVALID)
        if entry.processed_at is not None:
            return None

        # Convertir el payload a WebhookEvent vía el adapter del provider.
        # Aquí basta con cualquier gateway del provider — todos los
        # adapters de un mismo provider comparten parse_webhook_event.
        gateway = self._gateway_for_provider(entry.provider)

        import json
        event: WebhookEvent
        try:
            event = gateway.parse_webhook_event(json.dumps(entry.payload).encode('utf-8'))
        except Exception as exc:
            self.inbox_repo.mark_processed(entry.id, error=f'parse error: {exc}'[:512])
            raise AppException(AppErrorCode.PAY_WEBHOOK_INVALID, override_detail=str(exc))

        if not event.gateway_charge_id:
            self.inbox_repo.mark_processed(entry.id, error='no gateway_charge_id in event')
            return None

        charge = self.charge_repo.get_by_gateway_ref(entry.provider, event.gateway_charge_id)
        if charge is None:
            self.inbox_repo.mark_processed(entry.id, error='charge not found locally')
            return None

        if event.status is None:
            # Evento que no implica transición (ej. dispute.created sin estado nuevo).
            self.inbox_repo.mark_processed(entry.id, charge_id=charge.id)
            return charge

        synthetic = ChargeResult(
            gateway_provider=gateway.provider,
            gateway_charge_id=charge.gateway_charge_id,
            status=event.status,
            amount=charge.amount,
            currency=charge.currency,
            method_type=charge.method_type,
        )
        try:
            updated = _persist_state(
                self.charge_repo, charge.id, synthetic,
                previous_status=charge.status,
            )
        except ConflictException:
            # Reorden / evento ya superado: no es un error fatal.
            self.inbox_repo.mark_processed(entry.id, charge_id=charge.id, error='transition rejected by state machine')
            return charge

        self.inbox_repo.mark_processed(entry.id, charge_id=charge.id)
        return updated

    def _gateway_for_provider(self, provider: str):
        """Obtiene un gateway concreto del provider para llamar a ``parse_webhook_event``."""
        # En FASE 1 solo existe el simulator. Cuando haya adapters reales,
        # la factory o el registry sabrán resolverlos por nombre.
        from ..infrastructure.gateways.factory import get_payment_gateway
        from ..domain.enums import GatewayProvider
        try:
            target = GatewayProvider(provider)
        except ValueError:
            raise AppException(
                AppErrorCode.PAY_GATEWAY_UNAVAILABLE,
                override_detail=f'Provider desconocido en webhook: {provider!r}',
            )
        return get_payment_gateway(target)
