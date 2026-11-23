"""Unit tests for MinIO tenant export path and purge exclusions."""
from unittest import TestCase
from unittest.mock import MagicMock, patch

import pytest

from core.storage.domain.schemas import FileInfoSchema
from platform.features.company.tenant.company.domain.lifecycle import tenant_export_object_key
from platform.features.company.tenant.company.infrastructure.export_store import MinioTenantExportStore


pytestmark = pytest.mark.unit


def _file(object_name: str) -> FileInfoSchema:
    return FileInfoSchema(
        bucket='base',
        object_name=object_name,
        size=12,
        etag='etag',
        last_modified=None,
        content_type='application/json',
    )


class TestMinioTenantExportStore(TestCase):
    @patch('platform.features.company.tenant.company.infrastructure.export_store.UploadFileUseCase')
    def test_put_json_writes_under_tenant_deregistration(self, MockUpload):
        MockUpload.return_value.execute.return_value = MagicMock()
        store = MinioTenantExportStore(service=MagicMock())
        key = store.put_json('arisoft-sas', b'{"ok":true}')
        self.assertEqual(key, 'client/tenants/arisoft-sas/deregistration/export.json')
        self.assertEqual(key, tenant_export_object_key('arisoft-sas'))
        uploaded = MockUpload.return_value.execute.call_args.args[0]
        self.assertEqual(uploaded.bucket, 'base')
        self.assertEqual(uploaded.object_name, key)
        self.assertEqual(uploaded.content_type, 'application/json')

    @patch('platform.features.company.tenant.company.infrastructure.export_store.DeleteFileUseCase')
    @patch('platform.features.company.tenant.company.infrastructure.export_store.ListFilesUseCase')
    def test_delete_tenant_prefix_keeps_deregistration(self, MockList, MockDelete):
        MockList.return_value.execute.return_value = [
            _file('client/tenants/arisoft-sas/assets/profiles/pic-ana.jpg'),
            _file('client/tenants/arisoft-sas/warehouse/inventory/reference/ilustration/a.png'),
            _file('client/tenants/arisoft-sas/deregistration/export.json'),
            _file('client/tenants/arisoft-sas/deregistration/.keep'),
        ]
        store = MinioTenantExportStore(service=MagicMock())
        deleted = store.delete_tenant_prefix('arisoft-sas')
        self.assertEqual(deleted, 2)
        deleted_keys = [
            call.args[1] for call in MockDelete.return_value.execute.call_args_list
        ]
        self.assertEqual(
            deleted_keys,
            [
                'client/tenants/arisoft-sas/assets/profiles/pic-ana.jpg',
                'client/tenants/arisoft-sas/warehouse/inventory/reference/ilustration/a.png',
            ],
        )
