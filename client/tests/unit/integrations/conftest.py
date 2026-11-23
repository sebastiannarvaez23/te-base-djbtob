"""Fixtures compartidas — tests client integrations."""

from __future__ import annotations

import uuid
from typing import Dict, List

import pytest

from client.features.integrations.connections.profile.domain.interfaces import IIntegrationOrderRepository
from client.features.integrations.connections.profile.domain.schemas import (
    ConnectionSchema,
    CreateOrderFromIntegrationSchema,
    FieldMappingSchema,
    OrderIntegrationSchema,
    SyncRunSchema,
)


class InMemoryOrderRepo(IIntegrationOrderRepository):
    def __init__(self):
        self.orders: Dict[tuple, OrderIntegrationSchema] = {}

    def get_by_external_id(self, connection_id, external_id):
        return self.orders.get((connection_id, external_id))

    def create_from_integration(self, data: CreateOrderFromIntegrationSchema):
        oid = uuid.uuid4()
        row = OrderIntegrationSchema(
            id=oid,
            connection_id=data.connection_id,
            external_id=data.external_id,
            reference=data.reference,
            status=data.status,
            payload=data.payload,
            sync_status='SYNCED',
        )
        self.orders[(data.connection_id, data.external_id)] = row
        return row

    def update_from_integration(self, order_id, **fields):
        for key, row in self.orders.items():
            if row.id == order_id:
                updated = row.model_copy(update=fields)
                self.orders[key] = updated
                return updated
        raise ValueError('not found')

    def list_pending_outbound(self, connection_id, limit=100):
        return [
            o for o in self.orders.values()
            if o.connection_id == connection_id and o.sync_status == 'PENDING_OUTBOUND'
        ][:limit]

    def mark_synced(self, order_id):
        for key, row in self.orders.items():
            if row.id == order_id:
                self.orders[key] = row.model_copy(update={'sync_status': 'SYNCED'})
                return


class FakeConnectionRepo:
    def __init__(self, connector_key: str = 'fake'):
        self.connector_key = connector_key
        self.health_updates: list = []

    def get_by_id(self, id):
        return ConnectionSchema(
            id=id,
            connector_key=self.connector_key,
            name='Test',
            environment='CLIENT_TEST',
            config={'base_url': 'https://example.com'},
            status='ACTIVE',
            secret_id=None,
        )

    def update_health(self, id, **kwargs):
        self.health_updates.append(kwargs)


class FakeMappingRepo:
    def get_active(self, connection_id, entity, direction):
        return FieldMappingSchema(
            id=uuid.uuid4(),
            connection_id=connection_id,
            entity=entity,
            direction=direction,
            rules=[{'source': 'external_id', 'target': 'external_id'}],
            is_active=True,
        )


class FakeSyncRepo:
    def __init__(self):
        self.runs: List[SyncRunSchema] = []

    def create(self, connection_id, entity, direction, *, dry_run):
        run = SyncRunSchema(
            id=uuid.uuid4(),
            connection_id=connection_id,
            entity=entity,
            direction=direction,
            status='PENDING',
            dry_run=dry_run,
        )
        self.runs.append(run)
        return run

    def mark_running(self, id):
        pass

    def finish(self, id, status, stats, error_message=''):
        for i, run in enumerate(self.runs):
            if run.id == id:
                finished = run.model_copy(
                    update={'status': status, 'stats': stats, 'error_message': error_message},
                )
                self.runs[i] = finished
                return finished
        raise ValueError('missing run')
