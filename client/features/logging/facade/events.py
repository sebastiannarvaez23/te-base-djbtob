"""
logging/facade/events.py
────────────────────────
Dispatcher de eventos de dominio para logs que deben emitirse
como eventos (operations).

Implementación in-memory por defecto. Sustituible por Kafka, RabbitMQ, etc.
"""

import logging
from abc import ABC, abstractmethod
from typing import Callable

from pydantic import BaseModel

logger = logging.getLogger('app.api')


class IDomainEventDispatcher(ABC):
    """Port: despacha eventos de dominio para consumo asíncrono."""

    @abstractmethod
    def register(self, event_type: str, handler: Callable) -> None:
        """Registra un handler para un tipo de evento."""
        ...

    @abstractmethod
    def dispatch(self, event_type: str, payload: BaseModel) -> None:
        """Despacha un evento a todos los handlers registrados."""
        ...


class InMemoryEventDispatcher(IDomainEventDispatcher):
    """Implementación in-memory para eventos de dominio. Reemplazar con Kafka en producción."""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def register(self, event_type: str, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def dispatch(self, event_type: str, payload: BaseModel) -> None:
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(payload)
            except Exception as exc:
                logger.error(
                    'EVENT_HANDLER_ERROR event_type=%s handler=%s error=%s',
                    event_type, handler.__name__, str(exc),
                )
