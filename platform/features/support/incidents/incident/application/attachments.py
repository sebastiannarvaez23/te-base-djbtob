"""
Evidencia adjunta a incidencias / sugerencias.

``AttachIncidentMediaUseCase``: el reporter sube imágenes o MP4 justo después
de crear el reporte (ventana corta). Se valida cada archivo server-side, se
sube a object storage y luego se registran los metadatos con bloqueo de fila;
si el registro falla, los objetos subidos se eliminan (compensación).

``SignIncidentAttachmentsUseCase``: URLs GET efímeras para el portal admin.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from core.errors.codes import AppErrorCode
from core.errors.exceptions import (
    AppException,
    ConflictException,
    ValidationAppException,
)
from core.ids import uuid7
from core.trace import trace_layer
from platform.features.support.incidents.incident.application.admin_use_cases import (
    IncidentNotFound,
)
from platform.features.support.incidents.incident.domain.attachment_policy import (
    MAX_ATTACHMENTS,
    classify_media,
)
from platform.features.support.incidents.incident.domain.interfaces import (
    AttachmentLimitExceeded,
    IIncidentAttachmentRepository,
    IIncidentAttachmentStorage,
)
from platform.features.support.incidents.incident.domain.schemas import (
    AttachmentUpload,
    IncidentAttachment,
    IncidentAttachmentView,
    IncidentView,
)

logger = logging.getLogger('app.api')

OBJECT_PREFIX = 'admin/support/incidents'


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class AttachIncidentMediaUseCase:

    def __init__(
        self,
        repository: IIncidentAttachmentRepository,
        storage: IIncidentAttachmentStorage,
        *,
        window: timedelta,
        clock: Callable[[], datetime] = _utcnow,
    ):
        self._repo = repository
        self._storage = storage
        self._window = window
        self._clock = clock

    @trace_layer('application')
    def execute(
        self,
        *,
        incident_id: str,
        reporter_user_id: str,
        schema_name: str,
        files: list[AttachmentUpload],
    ) -> IncidentView:
        if not files:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        if len(files) > MAX_ATTACHMENTS:
            raise ValidationAppException(AppErrorCode.INCIDENT_ATTACHMENTS_LIMIT)

        incident = self._repo.get(incident_id)
        # Ajena o inexistente: misma respuesta, no se filtra existencia.
        if (
            incident is None
            or not reporter_user_id
            or incident.reporter_user_id != reporter_user_id
            or incident.schema_name != schema_name
        ):
            raise IncidentNotFound()

        reported_at = _parse_iso(incident.reported_at or incident.created_at)
        if reported_at is None or self._clock() - reported_at > self._window:
            raise ConflictException(AppErrorCode.INCIDENT_ATTACHMENTS_CLOSED)
        if len(incident.attachments) + len(files) > MAX_ATTACHMENTS:
            raise ValidationAppException(AppErrorCode.INCIDENT_ATTACHMENTS_LIMIT)

        accepted = []
        for upload in files:
            media = classify_media(upload.name, upload.content_type, upload.data)
            if media is None:
                raise ValidationAppException(AppErrorCode.INCIDENT_ATTACHMENT_INVALID)
            accepted.append((upload, media))

        stored: list[IncidentAttachment] = []
        uploaded_at = self._clock().isoformat()
        try:
            for upload, media in accepted:
                attachment_id = str(uuid7())
                object_name = f'{OBJECT_PREFIX}/{incident.id}/{attachment_id}.{media.extension}'
                self._storage.put(object_name, upload.data, media.content_type)
                stored.append(IncidentAttachment(
                    id=attachment_id,
                    object_name=object_name,
                    name=media.safe_name,
                    content_type=media.content_type,
                    size=len(upload.data),
                    kind=media.kind,
                    uploaded_at=uploaded_at,
                ))
            updated = self._repo.append_attachments(
                incident.id, stored, max_total=MAX_ATTACHMENTS,
            )
        except AttachmentLimitExceeded:
            self._discard(stored)
            raise ValidationAppException(AppErrorCode.INCIDENT_ATTACHMENTS_LIMIT)
        except AppException:
            self._discard(stored)
            raise
        except Exception as exc:
            self._discard(stored)
            logger.warning('INCIDENT_ATTACHMENT_STORE_FAILED id=%s error=%s', incident.id, exc)
            raise AppException(AppErrorCode.INCIDENT_ATTACHMENT_STORAGE) from exc

        if updated is None:
            self._discard(stored)
            raise IncidentNotFound()
        return updated

    def _discard(self, stored: list[IncidentAttachment]) -> None:
        for item in stored:
            try:
                self._storage.delete(item.object_name)
            except Exception as exc:
                logger.warning(
                    'INCIDENT_ATTACHMENT_ROLLBACK_FAILED object=%s error=%s',
                    item.object_name, exc,
                )


class SignIncidentAttachmentsUseCase:

    def __init__(self, storage: IIncidentAttachmentStorage):
        self._storage = storage

    @trace_layer('application')
    def execute(self, incident: IncidentView) -> list[IncidentAttachmentView]:
        views = []
        for item in incident.attachments:
            try:
                url = self._storage.signed_url(item.object_name)
            except Exception as exc:
                logger.warning(
                    'INCIDENT_ATTACHMENT_SIGN_FAILED object=%s error=%s',
                    item.object_name, exc,
                )
                url = ''
            views.append(to_attachment_view(item, url=url))
        return views


def to_attachment_view(item: IncidentAttachment, *, url: str = '') -> IncidentAttachmentView:
    return IncidentAttachmentView(
        id=item.id,
        name=item.name,
        content_type=item.content_type,
        size=item.size,
        kind=item.kind,
        uploaded_at=item.uploaded_at,
        url=url,
    )
