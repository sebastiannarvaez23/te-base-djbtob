"""
core/realtime/publisher.py
──────────────────────────
Puerto de SALIDA en tiempo real. Lo importante: se invoca desde **código
síncrono** (use cases, tareas Celery, repositorios) sin volverse async,
vía ``async_to_sync(channel_layer.group_send)``.

Degrada con elegancia: si el channel layer no está configurado (tests,
entorno sin Channels) hace no-op en vez de fallar — emitir en vivo es
best-effort; la fuente de verdad sigue siendo la base de datos.
"""

import logging
from abc import ABC, abstractmethod

from asgiref.sync import async_to_sync

from core.realtime.envelope import RealtimeMessage
from core.realtime.groups import RealtimeGroups

logger = logging.getLogger('app.api')


class IRealtimePublisher(ABC):
    """Port: empuja un mensaje a un usuario o grupo del channel layer."""

    @abstractmethod
    def to_user(self, schema: str, user_id, message: RealtimeMessage) -> None:
        ...

    @abstractmethod
    def to_group(self, group: str, message: RealtimeMessage) -> None:
        ...


class ChannelsRealtimePublisher(IRealtimePublisher):
    """Implementación sobre Django Channels (Redis channel layer)."""

    def to_user(self, schema: str, user_id, message: RealtimeMessage) -> None:
        self.to_group(RealtimeGroups.user(schema, user_id), message)

    def to_group(self, group: str, message: RealtimeMessage) -> None:
        layer = self._layer()
        if layer is None:
            logger.debug('realtime: channel layer no configurado; publish omitido group=%s', group)
            return
        try:
            async_to_sync(layer.group_send)(
                group,
                {'type': 'realtime.message', 'payload': message.model_dump(mode='json')},
            )
        except Exception as exc:  # nunca interrumpe el flujo principal
            logger.error('realtime publish falló group=%s error=%s', group, exc)

    @staticmethod
    def _layer():
        try:
            from channels.layers import get_channel_layer
            return get_channel_layer()
        except Exception:
            return None


class NullRealtimePublisher(IRealtimePublisher):
    """No-op. Útil para inyectar en tests sin tocar Channels."""

    def to_user(self, schema: str, user_id, message: RealtimeMessage) -> None:
        return None

    def to_group(self, group: str, message: RealtimeMessage) -> None:
        return None


class RealtimePublisherFactory:
    """Resuelve la implementación concreta del publisher (DIP)."""

    @classmethod
    def create(cls) -> IRealtimePublisher:
        return ChannelsRealtimePublisher()
