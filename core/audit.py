"""
core/audit.py
-------------
Helper centralizado de auditoria y logging de eventos.

Reemplaza los helpers _audit() y _log_warehouse_event() que estaban
duplicados en multiples vistas. El logging nunca interrumpe el flujo
principal: cada escritura corre en su propio savepoint para que un fallo
no aborte la transaccion del caso de uso, y el fallo queda registrado.
"""

import logging
from contextlib import nullcontext

from django.db import transaction

logger = logging.getLogger('app.errors')

INTEGRATION_ACTOR_KEY = 'integration_app'


def integration_actor(request) -> dict | None:
    """Integration Application behind the request; it is not a user, so it never fills ``user_id``."""
    from core.auth.integration.principal import IntegrationPrincipal

    user = getattr(request, 'user', None)
    if not isinstance(user, IntegrationPrincipal):
        return None
    return {'id': user.app_id, 'client_id': user.client_id, 'name': user.name}


def _persist(kind: str, write) -> None:
    try:
        with transaction.atomic():
            write()
    except Exception:
        logger.warning('Failed to persist %s log', kind, exc_info=True)


def _audit_schema_context(schema_name: str | None):
    """Switch to tenant schema when auditing from the public (SPA) host.

    ``audit_logs`` lives in TENANT_APPS only. Login/confirm/reset run on
    ``app.*`` (schema ``public``), so callers pass ``company.schema_name``.
    """
    if not schema_name:
        return nullcontext()
    from django.db import connection
    from django_tenants.utils import get_public_schema_name, schema_context

    public = get_public_schema_name()
    current = getattr(connection, 'schema_name', None) or public
    if schema_name == public or schema_name == current:
        return nullcontext()
    return schema_context(schema_name)


def audit_log(
    request,
    entity_type,
    entity_id,
    action,
    description=None,
    changes=None,
    *,
    schema_name: str | None = None,
):
    """Registra un log de auditoria sin interrumpir el flujo.

    ``schema_name``: tenant schema when the request is still on ``public``
    (e.g. client login on the SPA host).
    """
    def write():
        from client.features.logging.facade.factory import LogManagerFactory
        from client.features.logging.facade.context import LogContextBuilder
        from client.features.logging.audit_trail.audit.domain.schemas import AuditLogInputSchema

        ctx = LogContextBuilder.from_request(request)
        LogManagerFactory.create().audit(ctx, AuditLogInputSchema(
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            description=description,
            changes=changes,
        ))

    with _audit_schema_context(schema_name):
        _persist('audit', write)


def security_log(request, event_type, target_user_id=None, resource=None, detail=None):
    """Registra un log de seguridad sin interrumpir el flujo."""
    def write():
        from client.features.logging.facade.factory import LogManagerFactory
        from client.features.logging.facade.context import LogContextBuilder
        from client.features.logging.security.security.domain.schemas import SecurityLogInputSchema

        ctx = LogContextBuilder.from_request(request)
        LogManagerFactory.create().security(ctx, SecurityLogInputSchema(
            event_type=event_type,
            target_user_id=target_user_id,
            resource=resource,
            detail=detail,
        ))

    _persist('security', write)


def warehouse_event_log(
    request, event_type, reference_type=None, reference_id=None, payload=None, warehouse_id=None, refs=None,
):
    """Registra un evento de warehouse sin interrumpir el flujo.

    ``refs``: otros registros que el evento toca; su trazabilidad también lo muestra.
    """
    def write():
        from client.features.logging.facade.factory import LogManagerFactory
        from client.features.logging.facade.context import LogContextBuilder
        from client.features.logging.ops.operations.domain.schemas import (
            RELATED_REFS_KEY,
            WarehouseEventInputSchema,
        )

        data = dict(payload or {})
        actor = integration_actor(request)
        if actor:
            data[INTEGRATION_ACTOR_KEY] = actor
        related = sorted({str(ref) for ref in refs or () if ref})
        if related:
            data[RELATED_REFS_KEY] = related
        ctx = LogContextBuilder.from_request(request)
        LogManagerFactory.create().warehouse_event(ctx, WarehouseEventInputSchema(
            event_type=event_type,
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id else None,
            payload=data or None,
            warehouse_id=warehouse_id,
        ))

    _persist('warehouse event', write)
