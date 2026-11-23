"""
Puertos (interfaces) del sistema de incidencias — Dependency Inversion.

El repositorio y el notificador se añaden en fases posteriores.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from platform.features.support.incidents.incident.domain.schemas import (
    IncidentAttachment,
    IncidentCreate,
    IncidentView,
    TransactionLogEntry,
)


class AttachmentLimitExceeded(Exception):
    """Agregar los adjuntos superaría el máximo permitido por incidencia."""


class ISessionLogBuffer(ABC):
    """Port: anillo de las últimas N peticiones por sesión."""

    @abstractmethod
    def append_transaction(self, session_id: str, entry: TransactionLogEntry) -> None:
        """Empuja una petición al anillo de la sesión, conservando solo las últimas N."""
        ...

    @abstractmethod
    def snapshot(self, session_id: str) -> list[dict]:
        """Devuelve las peticiones capturadas en orden cronológico (más antigua primero)."""
        ...


class IIncidentDraftStore(ABC):
    """Port: almacén temporal del snapshot congelado en el 500, indexado por token."""

    @abstractmethod
    def save(self, token: str, draft: dict) -> None:
        """Guarda el draft con TTL bajo el token dado."""
        ...

    @abstractmethod
    def pop(self, token: str) -> Optional[dict]:
        """Devuelve y elimina el draft (single-use). ``None`` si no existe/expiró."""
        ...


class IIncidentRepository(ABC):
    """Port: persistencia de incidencias."""

    @abstractmethod
    def create(self, data: IncidentCreate) -> IncidentView:
        """Crea la incidencia (genera ``code`` secuencial). Puede lanzar en colisión de token."""
        ...

    @abstractmethod
    def get_by_token(self, token: str) -> Optional[IncidentView]:
        """Devuelve la incidencia asociada a un token, o ``None`` (idempotencia)."""
        ...

    @abstractmethod
    def get(self, incident_id: str) -> Optional[IncidentView]:
        ...

    @abstractmethod
    def list(self, filters: dict, limit: int = 50, offset: int = 0) -> list[IncidentView]:
        ...

    @abstractmethod
    def count(self, filters: dict) -> int:
        """Total de incidencias que cumplen los filtros (para paginación)."""
        ...

    @abstractmethod
    def update_status(self, incident_id: str, *, status: str,
                      assigned_admin_id: Optional[str] = None,
                      resolution_notes: Optional[str] = None) -> Optional[IncidentView]:
        ...

    @abstractmethod
    def purge(self, before, statuses) -> int:
        """Elimina incidencias en ``statuses`` no tocadas desde ``before``. Retorna cuántas."""
        ...


class IIncidentAttachmentRepository(ABC):
    """Port: metadatos de adjuntos de evidencia por incidencia."""

    @abstractmethod
    def get(self, incident_id: str) -> Optional[IncidentView]:
        ...

    @abstractmethod
    def append_attachments(
        self, incident_id: str, items: list[IncidentAttachment], *, max_total: int,
    ) -> Optional[IncidentView]:
        """Agrega adjuntos de forma atómica (con bloqueo de fila).

        ``None`` si la incidencia no existe; lanza ``AttachmentLimitExceeded``
        si el total superaría ``max_total``.
        """
        ...

    @abstractmethod
    def attachment_objects_for_purge(self, before, statuses) -> list[str]:
        """Rutas de objeto de los adjuntos de las incidencias que ``purge`` eliminaría."""
        ...


class IIncidentAttachmentStorage(ABC):
    """Port: object storage de la evidencia adjunta a incidencias."""

    @abstractmethod
    def put(self, object_name: str, data: bytes, content_type: str) -> None:
        ...

    @abstractmethod
    def delete(self, object_name: str) -> None:
        ...

    @abstractmethod
    def signed_url(self, object_name: str) -> str:
        """URL GET efímera; ``''`` si no se pudo firmar."""
        ...


class IIncidentNotifier(ABC):
    """Port: notifica al admin que se creó una incidencia."""

    @abstractmethod
    def notify_created(self, incident: IncidentView) -> None:
        ...


class IIncidentReporterNotifier(ABC):
    """Port: avisa al usuario reporter vía inbox (campanita) ante cambios de estado."""

    @abstractmethod
    def notify_status_changed(
        self,
        incident: IncidentView,
        *,
        previous_status: str,
        admin_id: str,
        admin_label: str,
    ) -> None:
        ...


class IFeatureRefResolver(ABC):
    """Port: resuelve ``feature_key`` → ``(module_id, functionality_id)``."""

    @abstractmethod
    def resolve(self, feature_key: str) -> tuple[str, str]:
        """Devuelve ids o ``('', '')`` si la clave no está en el catálogo."""
        ...
