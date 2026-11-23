"""Facade pública para otros módulos."""

from __future__ import annotations

import uuid

from client.features.integrations.connections.profile.models import SyncOutbox


def enqueue_order_outbound(order_id: uuid.UUID, connection_id: uuid.UUID | None = None) -> None:
    """Marca pedido para sync outbound (outbox mínimo Fase 2)."""
    from client.features.integrations.connections.profile.models import IntegrationOrder

    order = IntegrationOrder.objects.filter(id=order_id).first()
    if not order:
        return
    conn_id = connection_id or order.connection_id
    IntegrationOrder.objects.filter(id=order_id).update(sync_status='PENDING_OUTBOUND')
    SyncOutbox.objects.get_or_create(
        connection_id=conn_id,
        entity='order',
        entity_id=str(order_id),
        defaults={'payload': order.payload or {}, 'status': 'PENDING'},
    )


def on_order_status_changed(order_id: uuid.UUID, new_status: str) -> None:
    """Hook futuro: encola outbound al cambiar estado."""
    from client.features.integrations.connections.profile.models import IntegrationOrder

    IntegrationOrder.objects.filter(id=order_id).update(status=new_status)
    enqueue_order_outbound(order_id)
