from __future__ import annotations

from datetime import timedelta

from core.storage import (
    DeleteFileUseCase,
    GetPresignedUrlUseCase,
    ListFilesUseCase,
    PresignedUrlMethod,
    PresignedUrlSchema,
    UploadFileSchema,
    UploadFileUseCase,
)
from core.storage.profile_bucket import PROFILE_BUCKET
from platform.features.company.tenant.company.domain.interfaces import ITenantExportStore
from platform.features.company.tenant.company.domain.lifecycle import (
    STORAGE_BUCKET,
    tenant_deregistration_prefix,
    tenant_export_object_key,
    tenant_storage_prefix,
)


class MinioTenantExportStore(ITenantExportStore):
    def __init__(self, service=None):
        if service is None:
            from core.storage import MinioStorageService
            service = MinioStorageService()
        self.service = service
        self.bucket = STORAGE_BUCKET or PROFILE_BUCKET

    def put_json(self, schema_name: str, payload: bytes) -> str:
        object_name = tenant_export_object_key(schema_name)
        UploadFileUseCase(self.service).execute(UploadFileSchema(
            bucket=self.bucket,
            object_name=object_name,
            data=payload,
            content_type='application/json',
        ))
        return object_name

    def presign(self, object_key: str) -> str:
        return GetPresignedUrlUseCase(self.service).execute(PresignedUrlSchema(
            bucket=self.bucket,
            object_name=object_key,
            method=PresignedUrlMethod.GET,
            expires=timedelta(hours=1),
        ))

    def delete_tenant_prefix(self, schema_name: str) -> int:
        prefix = tenant_storage_prefix(schema_name)
        keep_prefix = tenant_deregistration_prefix(schema_name)
        try:
            files = ListFilesUseCase(self.service).execute(self.bucket, prefix=prefix)
        except Exception:
            return 0
        deleted = 0
        for item in files:
            if item.object_name.startswith(keep_prefix):
                continue
            try:
                DeleteFileUseCase(self.service).execute(self.bucket, item.object_name)
                deleted += 1
            except Exception:
                continue
        return deleted
