"""
MinioIncidentAttachmentStorage — evidencia de incidencias en el bucket compartido.

Los objetos viven bajo ``admin/support/incidents/`` (fuera de los patrones de
lectura anónima de ``profile_bucket``): solo se exponen vía URL firmada.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings

from core.storage.domain.schemas import (
    PresignedUrlMethod,
    PresignedUrlSchema,
    UploadFileSchema,
)
from core.storage.profile_bucket import PROFILE_BUCKET, ensure_profile_bucket
from platform.features.support.incidents.incident.domain.interfaces import (
    IIncidentAttachmentStorage,
)


class MinioIncidentAttachmentStorage(IIncidentAttachmentStorage):

    def __init__(self, service=None, bucket: str = PROFILE_BUCKET):
        if service is None:
            from core.storage.infrastructure.minio_storage import MinioStorageService
            service = MinioStorageService()
        self._service = service
        self._bucket = bucket

    def put(self, object_name: str, data: bytes, content_type: str) -> None:
        ensure_profile_bucket()
        self._service.upload_file(UploadFileSchema(
            bucket=self._bucket,
            object_name=object_name,
            data=data,
            content_type=content_type,
        ))

    def delete(self, object_name: str) -> None:
        self._service.delete_file(self._bucket, object_name)

    def signed_url(self, object_name: str) -> str:
        ttl = int(getattr(settings, 'INCIDENT_ATTACHMENT_URL_TTL_SECONDS', 600))
        return self._service.get_presigned_url(PresignedUrlSchema(
            bucket=self._bucket,
            object_name=object_name,
            method=PresignedUrlMethod.GET,
            expires=timedelta(seconds=ttl),
        ))
