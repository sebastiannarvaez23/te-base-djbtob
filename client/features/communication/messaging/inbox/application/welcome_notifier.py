"""Notificaciones de bienvenida en la campanita (inbox tenant)."""
from __future__ import annotations

import logging
import uuid

from django_tenants.utils import schema_context

from client.features.communication.messaging.inbox.domain.enums import ActorKind, NotificationKind
from client.features.communication.messaging.inbox.domain.schemas import NotificationPayload
from client.features.communication.messaging.inbox.facade.factory import NotificationManagerFactory
from platform.features.communication.messaging.inbox.domain.enums import NotificationLevel

logger = logging.getLogger('app.api')


def _display_name(user_name: str, fallback: str = '') -> str:
    name = (user_name or '').strip()
    return name or fallback or 'Usuario'


def _deliver_welcome(
    *,
    schema_name: str,
    user_id: uuid.UUID,
    title: str,
    body: str,
) -> None:
    if not schema_name or user_id is None:
        return
    payload = NotificationPayload(
        kind=NotificationKind.ADMIN_DIRECT,
        actor_kind=ActorKind.SYSTEM,
        actor_label='Base',
        title=title,
        body=body,
        level=NotificationLevel.SUCCESS,
    )
    with schema_context(schema_name):
        NotificationManagerFactory.create().deliver(schema_name, payload, [user_id])


def notify_executive_welcome(
    *,
    schema_name: str,
    user_id: uuid.UUID,
    user_name: str,
    company_name: str,
) -> None:
    """Bienvenida al administrador tras finalizar el registro de empresa."""
    try:
        name = _display_name(user_name)
        company = (company_name or '').strip() or 'tu empresa'
        body = (
            f'Hola {name}, tu empresa {company} ya está activa en la base. '
            'Desde configuración puedes invitar colaboradores, gestionar tu suscripción '
            'y preparar la operación.'
        )
        _deliver_welcome(
            schema_name=schema_name,
            user_id=user_id,
            title='Bienvenido a la base!',
            body=body,
        )
    except Exception:
        logger.exception(
            'notify_executive_welcome failed user=%s schema=%s',
            user_id, schema_name,
        )


def notify_collaborator_welcome(
    *,
    schema_name: str,
    user_id: uuid.UUID,
    user_name: str,
    company_name: str,
) -> None:
    """Bienvenida al colaborador creado por el administrador de la empresa."""
    try:
        name = _display_name(user_name)
        company = (company_name or '').strip() or 'la empresa'
        body = (
            f'Hola {name}, ya tienes acceso como colaborador de {company}. '
            'Revisa el menú lateral para conocer los módulos disponibles para tu rol.'
        )
        _deliver_welcome(
            schema_name=schema_name,
            user_id=user_id,
            title='Bienvenido al equipo',
            body=body,
        )
    except Exception:
        logger.exception(
            'notify_collaborator_welcome failed user=%s schema=%s',
            user_id, schema_name,
        )
