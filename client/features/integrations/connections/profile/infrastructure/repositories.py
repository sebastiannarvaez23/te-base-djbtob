"""Repositorios Django para integraciones tenant."""

from __future__ import annotations

import json
import uuid
from typing import List, Optional

from django.utils import timezone

from core.query.core import PaginatedQuery, PaginatedResult

from client.features.integrations.connections.profile.domain.interfaces import (
    IConnectionRepository,
    IFieldMappingRepository,
    IIntegrationOrderRepository,
    ISecretRepository,
    ISyncRunRepository,
)
from client.features.integrations.connections.profile.domain.schemas import (
    ConnectionSchema,
    CreateConnectionSchema,
    CreateFieldMappingSchema,
    CreateOrderFromIntegrationSchema,
    FieldMappingSchema,
    OrderIntegrationSchema,
    SyncRunSchema,
    UpdateConnectionSchema,
    UpdateFieldMappingSchema,
)
from client.features.integrations.connections.profile.models import (
    FieldMapping,
    IntegrationConnection,
    IntegrationOrder,
    SyncRun,
    TenantSecret,
)
from core.integrations.infrastructure.encrypted_secret_store import EncryptedSecretStore


class DjangoSecretRepository(ISecretRepository):

    def __init__(self, store: EncryptedSecretStore | None = None):
        self._crypto = store or EncryptedSecretStore()

    def store_encrypted(self, scope: str, secrets: dict[str, str]) -> uuid.UUID:
        del scope
        row = TenantSecret.objects.create(ciphertext=b'')
        enc_scope = f'secret:{row.id}'
        payload = json.dumps(secrets, sort_keys=True).encode('utf-8')
        row.ciphertext = self._crypto._encrypt(payload, enc_scope)
        row.save(update_fields=['ciphertext'])
        return row.id

    def get_decrypted(self, secret_id: uuid.UUID) -> dict[str, str]:
        row = TenantSecret.objects.filter(id=secret_id).first()
        if not row:
            return {}
        enc_scope = f'secret:{secret_id}'
        payload = self._crypto._decrypt(bytes(row.ciphertext), enc_scope)
        return json.loads(payload.decode('utf-8'))

    def rotate(self, secret_id: uuid.UUID, scope: str, secrets: dict[str, str]) -> None:
        del scope
        row = TenantSecret.objects.filter(id=secret_id).first()
        if not row:
            row = TenantSecret.objects.create(id=secret_id, ciphertext=b'')
        enc_scope = f'secret:{row.id}'
        payload = json.dumps(secrets, sort_keys=True).encode('utf-8')
        row.ciphertext = self._crypto._encrypt(payload, enc_scope)
        row.key_version = row.key_version + 1
        row.save()


class DjangoConnectionRepository(IConnectionRepository):

    def list_all(self, query: PaginatedQuery) -> PaginatedResult:
        from django.db.models import Q

        qs = IntegrationConnection.objects.all().order_by('name')
        f = query.filters
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'status' in f:
            qs = qs.filter(status=f['status'])
        if 'environment' in f:
            qs = qs.filter(environment=f['environment'])
        if 'connector_key' in f:
            qs = qs.filter(connector_key=f['connector_key'])
        if 'q' in f:
            qs = qs.filter(
                Q(name__icontains=f['q'])
                | Q(connector_key__icontains=f['q'])
                | Q(status__icontains=f['q'])
            )

        if query.unpaginated:
            items = [ConnectionSchema.model_validate(row) for row in qs]
            return PaginatedResult(
                items=items, total=len(items), page=0, page_size=0, total_pages=1,
            )

        total = qs.count()
        items = [
            ConnectionSchema.model_validate(row)
            for row in qs[query.offset: query.offset + query.limit]
        ]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items, total=total, page=query.page,
            page_size=query.page_size, total_pages=total_pages,
        )

    def get_by_id(self, id: uuid.UUID) -> Optional[ConnectionSchema]:
        row = IntegrationConnection.objects.filter(id=id).first()
        if not row:
            return None
        return ConnectionSchema(
            id=row.id,
            connector_key=row.connector_key,
            name=row.name,
            environment=row.environment,
            config=row.config or {},
            status=row.status,
            schedule_cron=row.schedule_cron or '',
            last_sync_at=row.last_sync_at,
            last_error=row.last_error or '',
            created_by=row.created_by,
            secret_id=row.secret_id,
        )

    def create(self, data: CreateConnectionSchema, secret_ref_id: Optional[uuid.UUID]) -> ConnectionSchema:
        row = IntegrationConnection.objects.create(
            connector_key=data.connector_key,
            name=data.name,
            environment=data.environment,
            config=data.config,
            schedule_cron=data.schedule_cron,
            created_by=data.created_by,
            secret_id=secret_ref_id,
        )
        return ConnectionSchema.model_validate(row)

    def update(self, id: uuid.UUID, data: UpdateConnectionSchema) -> Optional[ConnectionSchema]:
        row = IntegrationConnection.objects.filter(id=id).first()
        if not row:
            return None
        for field in ('name', 'environment', 'config', 'status', 'schedule_cron'):
            value = getattr(data, field)
            if value is not None:
                setattr(row, field, value)
        row.save()
        return ConnectionSchema.model_validate(row)

    def update_health(
        self, id: uuid.UUID, *, status: str | None = None, last_error: str = '', last_sync_at=None,
    ) -> None:
        row = IntegrationConnection.objects.filter(id=id).first()
        if not row:
            return
        if status is not None:
            row.status = status
        if last_error:
            row.last_error = last_error
        if last_sync_at is not None:
            row.last_sync_at = last_sync_at
        row.save()


class DjangoFieldMappingRepository(IFieldMappingRepository):

    def list_by_connection(self, connection_id: uuid.UUID) -> List[FieldMappingSchema]:
        qs = FieldMapping.objects.filter(connection_id=connection_id).order_by('entity', 'direction')
        return [self._to_schema(row) for row in qs]

    def get_active(self, connection_id: uuid.UUID, entity: str, direction: str) -> Optional[FieldMappingSchema]:
        row = FieldMapping.objects.filter(
            connection_id=connection_id, entity=entity, direction=direction, is_active=True,
        ).first()
        return self._to_schema(row) if row else None

    def create(self, data: CreateFieldMappingSchema) -> FieldMappingSchema:
        row = FieldMapping.objects.create(**data.model_dump())
        return self._to_schema(row)

    def update(self, id: uuid.UUID, data: UpdateFieldMappingSchema) -> Optional[FieldMappingSchema]:
        row = FieldMapping.objects.filter(id=id).first()
        if not row:
            return None
        if data.rules is not None:
            row.rules = data.rules
        if data.is_active is not None:
            row.is_active = data.is_active
        row.save()
        return self._to_schema(row)

    def delete(self, id: uuid.UUID) -> bool:
        deleted, _ = FieldMapping.objects.filter(id=id).delete()
        return deleted > 0

    @staticmethod
    def _to_schema(row: FieldMapping) -> FieldMappingSchema:
        return FieldMappingSchema(
            id=row.id,
            connection_id=row.connection_id,
            entity=row.entity,
            direction=row.direction,
            rules=row.rules or [],
            is_active=row.is_active,
        )


class DjangoSyncRunRepository(ISyncRunRepository):

    def create(self, connection_id: uuid.UUID, entity: str, direction: str, *, dry_run: bool) -> SyncRunSchema:
        row = SyncRun.objects.create(
            connection_id=connection_id,
            entity=entity,
            direction=direction,
            dry_run=dry_run,
        )
        return self._to_schema(row)

    def mark_running(self, id: uuid.UUID) -> None:
        SyncRun.objects.filter(id=id).update(status='RUNNING', started_at=timezone.now())

    def finish(self, id: uuid.UUID, status: str, stats: dict, error_message: str = '') -> SyncRunSchema:
        row = SyncRun.objects.filter(id=id).first()
        if not row:
            raise ValueError('sync run not found')
        row.status = status
        row.stats = stats
        row.error_message = error_message
        row.finished_at = timezone.now()
        row.save()
        return self._to_schema(row)

    def list_recent(self, connection_id: uuid.UUID | None = None, limit: int = 50) -> List[SyncRunSchema]:
        qs = SyncRun.objects.all().order_by('-created_at')
        if connection_id:
            qs = qs.filter(connection_id=connection_id)
        return [self._to_schema(row) for row in qs[:limit]]

    @staticmethod
    def _to_schema(row: SyncRun) -> SyncRunSchema:
        return SyncRunSchema(
            id=row.id,
            connection_id=row.connection_id,
            entity=row.entity,
            direction=row.direction,
            status=row.status,
            stats=row.stats or {},
            dry_run=row.dry_run,
            error_message=row.error_message or '',
            started_at=row.started_at,
            finished_at=row.finished_at,
        )


class DjangoIntegrationOrderRepository(IIntegrationOrderRepository):

    def get_by_external_id(self, connection_id: uuid.UUID, external_id: str) -> Optional[OrderIntegrationSchema]:
        row = IntegrationOrder.objects.filter(
            connection_id=connection_id, external_id=external_id,
        ).first()
        return self._to_schema(row) if row else None

    def create_from_integration(self, data: CreateOrderFromIntegrationSchema) -> OrderIntegrationSchema:
        row = IntegrationOrder.objects.create(
            connection_id=data.connection_id,
            external_id=data.external_id,
            reference=data.reference,
            status=data.status,
            payload=data.payload,
            sync_status='SYNCED',
            last_sync_at=timezone.now(),
        )
        return self._to_schema(row)

    def update_from_integration(self, order_id: uuid.UUID, **fields) -> OrderIntegrationSchema:
        row = IntegrationOrder.objects.filter(id=order_id).first()
        if not row:
            raise ValueError('order not found')
        for key, value in fields.items():
            setattr(row, key, value)
        row.last_sync_at = timezone.now()
        row.save()
        return self._to_schema(row)

    def list_pending_outbound(self, connection_id: uuid.UUID, limit: int = 100) -> List[OrderIntegrationSchema]:
        rows = IntegrationOrder.objects.filter(
            connection_id=connection_id, sync_status='PENDING_OUTBOUND',
        ).order_by('created_at')[:limit]
        return [self._to_schema(row) for row in rows]

    def mark_synced(self, order_id: uuid.UUID) -> None:
        IntegrationOrder.objects.filter(id=order_id).update(
            sync_status='SYNCED', last_sync_at=timezone.now(),
        )

    @staticmethod
    def _to_schema(row: IntegrationOrder) -> OrderIntegrationSchema:
        return OrderIntegrationSchema(
            id=row.id,
            connection_id=row.connection_id,
            external_id=row.external_id,
            reference=row.reference,
            status=row.status,
            payload=row.payload or {},
            sync_status=row.sync_status,
            last_sync_at=row.last_sync_at,
        )
