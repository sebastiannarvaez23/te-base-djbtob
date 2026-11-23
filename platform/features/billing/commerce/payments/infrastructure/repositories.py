"""
Repositorios Django para el dominio de pagos.

Implementan los puertos definidos en :mod:`...domain.interfaces`. La
única capa que toca el ORM. Cualquier cosa que necesite leer/escribir
``billing_charges`` debe pasar por aquí.
"""

import uuid
from typing import List, Optional

from django.db import transaction
from django.utils import timezone

from core.query.core import PaginatedQuery, PaginatedResult

from ..domain.enums import ChargeStatus
from ..domain.interfaces import (
    IChargeRepository,
    IIdempotencyStore,
    IWebhookInboxRepository,
)
from ..domain.schemas import (
    ChargeAttemptSchema,
    ChargeSchema,
    CreateChargeSchema,
    CreateWebhookInboxEntrySchema,
    IdempotencyRecordSchema,
    UpdateChargeStateSchema,
    WebhookInboxEntrySchema,
)
from ..domain.state_machine import assert_transition
from ..models import Charge, ChargeAttempt, IdempotencyKey, WebhookInbox


_CHARGE_FIELDS = (
    'id', 'idempotency_key', 'gateway_provider', 'gateway_charge_id',
    'company_id', 'invoice_id', 'payment_method_id', 'company_subscription_id',
    'amount', 'currency', 'method_type', 'description',
    'status', 'next_action_type', 'next_action_url',
    'failure_code', 'failure_message',
    'authorized_at', 'captured_at', 'canceled_at', 'refunded_amount',
    'metadata', 'created_at', 'updated_at',
)

_ATTEMPT_FIELDS = (
    'id', 'charge_id', 'operation', 'gateway_provider',
    'request_payload', 'response_payload',
    'result', 'error_message', 'attempted_at',
)

_INBOX_FIELDS = (
    'id', 'provider', 'external_event_id', 'event_type', 'payload',
    'signature', 'signature_verified', 'received_at',
    'processed_at', 'processing_error', 'charge_id',
)

_IDEM_FIELDS = ('key', 'scope', 'request_hash', 'response_payload', 'created_at', 'expires_at')


# ── Charge repository ─────────────────────────────────────────────────────────


class DjangoChargeRepository(IChargeRepository):

    def get_by_id(self, id: uuid.UUID) -> Optional[ChargeSchema]:
        row = Charge.objects.filter(id=id).values(*_CHARGE_FIELDS).first()
        return ChargeSchema(**row) if row else None

    def get_by_idempotency_key(self, key: str) -> Optional[ChargeSchema]:
        row = Charge.objects.filter(idempotency_key=key).values(*_CHARGE_FIELDS).first()
        return ChargeSchema(**row) if row else None

    def get_by_gateway_ref(self, provider: str, gateway_charge_id: str) -> Optional[ChargeSchema]:
        row = (
            Charge.objects
            .filter(gateway_provider=provider, gateway_charge_id=gateway_charge_id)
            .values(*_CHARGE_FIELDS)
            .first()
        )
        return ChargeSchema(**row) if row else None

    def list_by_company(self, company_id: uuid.UUID, query: PaginatedQuery) -> PaginatedResult:
        qs = Charge.objects.filter(company_id=company_id).order_by('-created_at')
        f = query.filters

        if 'status' in f:
            qs = qs.filter(status=f['status'])
        if 'method_type' in f:
            qs = qs.filter(method_type=f['method_type'])
        if 'invoice_id' in f:
            qs = qs.filter(invoice_id=f['invoice_id'])
        if 'from' in f:
            qs = qs.filter(created_at__gte=f['from'])
        if 'to' in f:
            qs = qs.filter(created_at__lte=f['to'])
        if 'amount_min' in f:
            qs = qs.filter(amount__gte=f['amount_min'])
        if 'amount_max' in f:
            qs = qs.filter(amount__lte=f['amount_max'])

        total = qs.count()
        rows = qs.values(*_CHARGE_FIELDS)[query.offset: query.offset + query.limit]
        items = [ChargeSchema(**row) for row in rows]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
        )

    def create(self, data: CreateChargeSchema) -> ChargeSchema:
        obj = Charge.objects.create(**data.model_dump())
        return ChargeSchema.model_validate(obj)

    @transaction.atomic
    def transition(self, id: uuid.UUID, data: UpdateChargeStateSchema) -> Optional[ChargeSchema]:
        """
        Aplica una transición con validación de state machine.

        Toma el lock de fila (``select_for_update``) para evitar carreras
        entre webhook entrante y respuesta síncrona del gateway.
        """
        try:
            charge = Charge.objects.select_for_update().get(id=id)
        except Charge.DoesNotExist:
            return None

        current = ChargeStatus(charge.status)
        assert_transition(current, data.status)

        charge.status = data.status.value
        if data.gateway_charge_id is not None:
            charge.gateway_charge_id = data.gateway_charge_id
        if data.next_action_type:
            charge.next_action_type = data.next_action_type
        if data.next_action_url:
            charge.next_action_url = data.next_action_url
        if data.failure_code:
            charge.failure_code = data.failure_code
        if data.failure_message:
            charge.failure_message = data.failure_message
        if data.authorized_at is not None:
            charge.authorized_at = data.authorized_at
        if data.captured_at is not None:
            charge.captured_at = data.captured_at
        if data.canceled_at is not None:
            charge.canceled_at = data.canceled_at
        if data.refunded_amount is not None:
            charge.refunded_amount = data.refunded_amount
        if data.metadata is not None:
            # merge superficial; no pisa los metadatos anteriores
            merged = {**(charge.metadata or {}), **data.metadata}
            charge.metadata = merged

        charge.save()
        return ChargeSchema.model_validate(charge)

    def add_attempt(self, attempt: ChargeAttemptSchema) -> ChargeAttemptSchema:
        obj = ChargeAttempt.objects.create(**attempt.model_dump(exclude={'id', 'attempted_at'}))
        return ChargeAttemptSchema.model_validate(obj)

    def bind_period(self, charge_id: uuid.UUID, period_id: uuid.UUID) -> Optional[ChargeSchema]:
        updated = Charge.objects.filter(id=charge_id).update(company_subscription_id=period_id)
        if not updated:
            return None
        return self.get_by_id(charge_id)


# ── Webhook inbox repository ──────────────────────────────────────────────────


class DjangoWebhookInboxRepository(IWebhookInboxRepository):

    def get_by_external_id(self, provider: str, external_event_id: str) -> Optional[WebhookInboxEntrySchema]:
        row = (
            WebhookInbox.objects
            .filter(provider=provider, external_event_id=external_event_id)
            .values(*_INBOX_FIELDS)
            .first()
        )
        return WebhookInboxEntrySchema(**row) if row else None

    def create(self, data: CreateWebhookInboxEntrySchema) -> WebhookInboxEntrySchema:
        obj = WebhookInbox.objects.create(**data.model_dump())
        return WebhookInboxEntrySchema.model_validate(obj)

    def mark_processed(
        self,
        id: uuid.UUID,
        charge_id: Optional[uuid.UUID] = None,
        error: str = '',
    ) -> Optional[WebhookInboxEntrySchema]:
        changes = {
            'processed_at': timezone.now(),
            'processing_error': error,
        }
        if charge_id is not None:
            changes['charge_id'] = charge_id
        updated = WebhookInbox.objects.filter(id=id).update(**changes)
        if not updated:
            return None
        row = WebhookInbox.objects.filter(id=id).values(*_INBOX_FIELDS).first()
        return WebhookInboxEntrySchema(**row) if row else None

    def list_unprocessed(self, limit: int = 100) -> List[WebhookInboxEntrySchema]:
        rows = (
            WebhookInbox.objects
            .filter(processed_at__isnull=True)
            .order_by('received_at')
            .values(*_INBOX_FIELDS)[:limit]
        )
        return [WebhookInboxEntrySchema(**row) for row in rows]


# ── Idempotency store ─────────────────────────────────────────────────────────


class DjangoIdempotencyStore(IIdempotencyStore):

    def get(self, scope: str, key: str) -> Optional[IdempotencyRecordSchema]:
        row = (
            IdempotencyKey.objects
            .filter(scope=scope, key=key, expires_at__gt=timezone.now())
            .values(*_IDEM_FIELDS)
            .first()
        )
        return IdempotencyRecordSchema(**row) if row else None

    def put(
        self,
        scope: str,
        key: str,
        request_hash: str,
        response_payload: dict,
        ttl_seconds: int = 24 * 60 * 60,
    ) -> IdempotencyRecordSchema:
        from datetime import timedelta
        expires_at = timezone.now() + timedelta(seconds=ttl_seconds)
        obj, _ = IdempotencyKey.objects.update_or_create(
            key=key,
            defaults={
                'scope': scope,
                'request_hash': request_hash,
                'response_payload': response_payload,
                'expires_at': expires_at,
            },
        )
        return IdempotencyRecordSchema.model_validate(obj)

    def purge_expired(self) -> int:
        deleted, _ = IdempotencyKey.objects.filter(expires_at__lte=timezone.now()).delete()
        return deleted
