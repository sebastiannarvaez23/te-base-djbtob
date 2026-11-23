"""
Unit tests for MinioStorageService (infrastructure adapter).

The Minio client and Django settings are mocked so no real MinIO
connection is required. Each test verifies that the service:
  - Calls the correct SDK method with the right arguments
  - Maps SDK results to the expected domain schema
  - Translates S3Error codes into the correct AppException subclass
  - Translates MaxRetryError (connection failures) into ServerException
"""
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

from minio.error import S3Error
from urllib3.exceptions import MaxRetryError

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ConflictException, NotFoundException, ServerException
from core.storage.domain.schemas import (
    BucketSchema,
    CreateBucketSchema,
    FileInfoSchema,
    PresignedUrlMethod,
    PresignedUrlSchema,
    ReplaceFileSchema,
    UploadFileSchema,
)
from core.storage.infrastructure.minio_storage import MinioStorageService


# ── Test helpers ───────────────────────────────────────────────────────────────

def _s3_error(code: str) -> S3Error:
    """Create a minimal S3Error. response=None is safe since our code only reads .code."""
    return S3Error(
        code=code,
        message='test error',
        resource='/',
        request_id='test-request-id',
        host_id='test-host-id',
        response=None,
    )


def _max_retry_error() -> MaxRetryError:
    return MaxRetryError(pool=None, url='http://minio:9000')


def _minio_object(object_name: str, size: int = 512, etag: str = 'abc', is_dir: bool = False):
    obj = MagicMock()
    obj.object_name = object_name
    obj.size = size
    obj.etag = etag
    obj.last_modified = datetime(2024, 1, 1, tzinfo=timezone.utc)
    obj.is_dir = is_dir
    return obj


def _minio_bucket(name: str):
    b = MagicMock()
    b.name = name
    b.creation_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return b


def _stat(size=1024, content_type='application/pdf', etag='etag123', metadata=None):
    stat = MagicMock()
    stat.size = size
    stat.content_type = content_type
    stat.etag = etag
    stat.last_modified = datetime(2024, 6, 1, tzinfo=timezone.utc)
    stat.metadata = metadata or {}
    return stat


# ── Base test class ────────────────────────────────────────────────────────────

class _MinioServiceTestCase(TestCase):
    """
    Base class that patches Minio and settings before each test.
    Subclasses access self.service and self.client.
    """

    def setUp(self):
        # Implementation lives in necore; base module is a strangler re-export.
        settings_patcher = patch(
            'necore.storage.infrastructure.minio_storage.settings'
        )
        minio_patcher = patch(
            'necore.storage.infrastructure.minio_storage.Minio'
        )

        self.mock_settings = settings_patcher.start()
        self.mock_settings.MINIO_ENDPOINT   = '127.0.0.1:3210'
        self.mock_settings.MINIO_ACCESS_KEY = 'test-key'
        self.mock_settings.MINIO_SECRET_KEY = 'test-secret'
        self.mock_settings.MINIO_USE_SSL    = False

        self.MockMinio = minio_patcher.start()
        self.client    = MagicMock()
        self.MockMinio.return_value = self.client

        self.service = MinioStorageService()

        self.addCleanup(settings_patcher.stop)
        self.addCleanup(minio_patcher.stop)


# ── Initialization ─────────────────────────────────────────────────────────────

class TestMinioStorageServiceInit(_MinioServiceTestCase):

    def test_creates_client_with_settings(self):
        self.MockMinio.assert_called_once_with(
            endpoint='127.0.0.1:3210',
            access_key='test-key',
            secret_key='test-secret',
            secure=False,
        )

    def test_client_stored_as_instance_attribute(self):
        self.assertIs(self.service._client, self.client)


# ── Bucket operations ──────────────────────────────────────────────────────────

class TestMinioStorageServiceCreateBucket(_MinioServiceTestCase):

    # Success

    def test_returns_bucket_schema_on_success(self):
        self.client.make_bucket.return_value = None

        result = self.service.create_bucket(CreateBucketSchema(bucket='invoices'))

        self.assertIsInstance(result, BucketSchema)
        self.assertEqual(result.name, 'invoices')

    def test_passes_bucket_name_and_region_to_sdk(self):
        self.service.create_bucket(
            CreateBucketSchema(bucket='docs', region='us-east-1')
        )

        self.client.make_bucket.assert_called_once_with('docs', location='us-east-1')

    def test_bucket_name_in_schema_matches_input(self):
        self.client.make_bucket.return_value = None

        result = self.service.create_bucket(CreateBucketSchema(bucket='my-bucket'))

        self.assertEqual(result.name, 'my-bucket')

    # Failure

    def test_raises_conflict_on_bucket_already_owned(self):
        self.client.make_bucket.side_effect = _s3_error('BucketAlreadyOwnedByYou')

        with self.assertRaises(ConflictException) as ctx:
            self.service.create_bucket(CreateBucketSchema(bucket='existing'))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_ALREADY_EXISTS)

    def test_raises_server_error_on_other_s3_error(self):
        self.client.make_bucket.side_effect = _s3_error('InternalError')

        with self.assertRaises(ServerException) as ctx:
            self.service.create_bucket(CreateBucketSchema(bucket='my-bucket'))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)

    def test_raises_server_error_on_connection_failure(self):
        self.client.make_bucket.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.create_bucket(CreateBucketSchema(bucket='my-bucket'))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)


class TestMinioStorageServiceDeleteBucket(_MinioServiceTestCase):

    # Success

    def test_returns_true_on_success(self):
        result = self.service.delete_bucket('test-bucket')

        self.assertTrue(result)
        self.client.remove_bucket.assert_called_once_with('test-bucket')

    def test_force_removes_all_objects_before_deleting_bucket(self):
        obj1 = _minio_object('file1.pdf')
        obj2 = _minio_object('file2.pdf')
        self.client.list_objects.return_value = iter([obj1, obj2])
        self.client.remove_objects.return_value = iter([])

        self.service.delete_bucket('test-bucket', force=True)

        self.client.list_objects.assert_called_once_with('test-bucket', recursive=True)
        self.client.remove_objects.assert_called_once()
        self.client.remove_bucket.assert_called_once_with('test-bucket')

    def test_skips_remove_objects_when_not_force(self):
        self.service.delete_bucket('test-bucket', force=False)

        self.client.list_objects.assert_not_called()
        self.client.remove_objects.assert_not_called()

    # Failure

    def test_raises_not_found_on_no_such_bucket(self):
        self.client.remove_bucket.side_effect = _s3_error('NoSuchBucket')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.delete_bucket('ghost-bucket')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_raises_server_error_on_other_s3_error(self):
        self.client.remove_bucket.side_effect = _s3_error('AccessDenied')

        with self.assertRaises(ServerException) as ctx:
            self.service.delete_bucket('my-bucket')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)

    def test_raises_server_error_on_connection_failure(self):
        self.client.remove_bucket.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.delete_bucket('my-bucket')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)


class TestMinioStorageServiceBucketExists(_MinioServiceTestCase):

    def test_returns_true_when_bucket_exists(self):
        self.client.bucket_exists.return_value = True

        self.assertTrue(self.service.bucket_exists('test-bucket'))

    def test_returns_false_when_bucket_does_not_exist(self):
        self.client.bucket_exists.return_value = False

        self.assertFalse(self.service.bucket_exists('ghost-bucket'))

    def test_returns_false_on_s3_error(self):
        self.client.bucket_exists.side_effect = _s3_error('InternalError')

        self.assertFalse(self.service.bucket_exists('test-bucket'))

    def test_returns_false_on_connection_failure(self):
        self.client.bucket_exists.side_effect = _max_retry_error()

        self.assertFalse(self.service.bucket_exists('test-bucket'))


class TestMinioStorageServiceListBuckets(_MinioServiceTestCase):

    def test_returns_all_buckets_mapped_to_schema(self):
        self.client.list_buckets.return_value = [
            _minio_bucket('invoices'),
            _minio_bucket('documents'),
        ]

        result = self.service.list_buckets()

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], BucketSchema)
        names = [b.name for b in result]
        self.assertIn('invoices', names)
        self.assertIn('documents', names)

    def test_returns_empty_list_when_no_buckets(self):
        self.client.list_buckets.return_value = []

        result = self.service.list_buckets()

        self.assertEqual(result, [])

    def test_raises_server_error_on_s3_error(self):
        self.client.list_buckets.side_effect = _s3_error('AccessDenied')

        with self.assertRaises(ServerException) as ctx:
            self.service.list_buckets()

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)

    def test_raises_server_error_on_connection_failure(self):
        self.client.list_buckets.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.list_buckets()

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)


# ── File operations ────────────────────────────────────────────────────────────

class TestMinioStorageServiceUploadFile(_MinioServiceTestCase):

    def _schema(self, **overrides):
        defaults = dict(
            bucket='test-bucket',
            object_name='docs/report.pdf',
            data=b'PDF content',
            content_type='application/pdf',
            metadata={'env': 'test'},
        )
        defaults.update(overrides)
        return UploadFileSchema(**defaults)

    # Success

    def test_returns_file_info_with_etag_from_sdk(self):
        put_result = MagicMock()
        put_result.etag = 'etag-123'
        self.client.put_object.return_value = put_result

        result = self.service.upload_file(self._schema())

        self.assertIsInstance(result, FileInfoSchema)
        self.assertEqual(result.etag, 'etag-123')

    def test_file_info_contains_correct_bucket_and_object_name(self):
        put_result = MagicMock()
        put_result.etag = 'abc'
        self.client.put_object.return_value = put_result

        result = self.service.upload_file(
            self._schema(bucket='invoices', object_name='2024/inv-001.pdf')
        )

        self.assertEqual(result.bucket, 'invoices')
        self.assertEqual(result.object_name, '2024/inv-001.pdf')

    def test_file_info_size_matches_data_length(self):
        put_result = MagicMock()
        put_result.etag = 'abc'
        self.client.put_object.return_value = put_result
        data = b'x' * 512

        result = self.service.upload_file(self._schema(data=data))

        self.assertEqual(result.size, 512)

    def test_passes_correct_arguments_to_sdk(self):
        put_result = MagicMock()
        put_result.etag = 'abc'
        self.client.put_object.return_value = put_result

        schema = self._schema(
            bucket='docs',
            object_name='contract.pdf',
            data=b'content',
            content_type='application/pdf',
            metadata={'author': 'admin'},
        )
        self.service.upload_file(schema)

        args, kwargs = self.client.put_object.call_args
        self.assertEqual(kwargs['bucket_name'], 'docs')
        self.assertEqual(kwargs['object_name'], 'contract.pdf')
        self.assertEqual(kwargs['length'], len(b'content'))
        self.assertEqual(kwargs['content_type'], 'application/pdf')

    # Failure

    def test_raises_server_error_on_s3_error(self):
        self.client.put_object.side_effect = _s3_error('InternalError')

        with self.assertRaises(ServerException) as ctx:
            self.service.upload_file(self._schema())

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_UPLOAD_FAILED)

    def test_raises_server_error_on_connection_failure(self):
        self.client.put_object.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.upload_file(self._schema())

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)


class TestMinioStorageServiceDownloadFile(_MinioServiceTestCase):

    # Success

    def test_returns_file_bytes_on_success(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b'file bytes'
        self.client.get_object.return_value = mock_response

        result = self.service.download_file('test-bucket', 'file.pdf')

        self.assertEqual(result, b'file bytes')

    def test_passes_correct_bucket_and_object_to_sdk(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b''
        self.client.get_object.return_value = mock_response

        self.service.download_file('my-bucket', 'path/doc.pdf')

        self.client.get_object.assert_called_once_with('my-bucket', 'path/doc.pdf')

    # Failure

    def test_raises_not_found_on_no_such_key(self):
        self.client.get_object.side_effect = _s3_error('NoSuchKey')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.download_file('test-bucket', 'ghost.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_FILE_NOT_FOUND)

    def test_raises_not_found_on_no_such_object(self):
        self.client.get_object.side_effect = _s3_error('NoSuchObject')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.download_file('test-bucket', 'ghost.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_FILE_NOT_FOUND)

    def test_raises_not_found_on_no_such_bucket(self):
        self.client.get_object.side_effect = _s3_error('NoSuchBucket')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.download_file('ghost-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_raises_server_error_on_other_s3_error(self):
        self.client.get_object.side_effect = _s3_error('AccessDenied')

        with self.assertRaises(ServerException) as ctx:
            self.service.download_file('test-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)

    def test_raises_server_error_on_connection_failure(self):
        self.client.get_object.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.download_file('test-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)


class TestMinioStorageServiceDeleteFile(_MinioServiceTestCase):

    # Success

    def test_returns_true_on_success(self):
        result = self.service.delete_file('test-bucket', 'file.pdf')

        self.assertTrue(result)

    def test_passes_correct_bucket_and_object_to_sdk(self):
        self.service.delete_file('my-bucket', 'docs/contract.pdf')

        self.client.remove_object.assert_called_once_with('my-bucket', 'docs/contract.pdf')

    # Failure

    def test_raises_not_found_on_no_such_bucket(self):
        self.client.remove_object.side_effect = _s3_error('NoSuchBucket')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.delete_file('ghost-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_raises_server_error_on_other_s3_error(self):
        self.client.remove_object.side_effect = _s3_error('InternalError')

        with self.assertRaises(ServerException) as ctx:
            self.service.delete_file('test-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_DELETE_FAILED)

    def test_raises_server_error_on_connection_failure(self):
        self.client.remove_object.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.delete_file('test-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)


class TestMinioStorageServiceReplaceFile(_MinioServiceTestCase):
    """
    replace_file delegates to upload_file (PUT overwrites in MinIO).
    These tests verify the delegation contract and that the schema
    is correctly converted.
    """

    def test_delegates_to_put_object(self):
        put_result = MagicMock()
        put_result.etag = 'new-etag'
        self.client.put_object.return_value = put_result

        schema = ReplaceFileSchema(
            bucket='test-bucket',
            object_name='docs/file.pdf',
            data=b'new content',
            content_type='application/pdf',
        )
        result = self.service.replace_file(schema)

        self.client.put_object.assert_called_once()
        self.assertIsInstance(result, FileInfoSchema)

    def test_returns_updated_file_info_with_new_etag(self):
        put_result = MagicMock()
        put_result.etag = 'updated-etag'
        self.client.put_object.return_value = put_result

        schema = ReplaceFileSchema(
            bucket='test-bucket',
            object_name='doc.pdf',
            data=b'updated',
            content_type='application/pdf',
        )
        result = self.service.replace_file(schema)

        self.assertEqual(result.etag, 'updated-etag')

    def test_propagates_upload_error(self):
        self.client.put_object.side_effect = _s3_error('InternalError')

        schema = ReplaceFileSchema(
            bucket='test-bucket',
            object_name='doc.pdf',
            data=b'data',
            content_type='application/pdf',
        )
        with self.assertRaises(ServerException) as ctx:
            self.service.replace_file(schema)

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_UPLOAD_FAILED)


class TestMinioStorageServiceFileExists(_MinioServiceTestCase):

    def test_returns_true_when_stat_succeeds(self):
        self.client.stat_object.return_value = _stat()

        self.assertTrue(self.service.file_exists('test-bucket', 'file.pdf'))

    def test_returns_false_on_no_such_key(self):
        self.client.stat_object.side_effect = _s3_error('NoSuchKey')

        self.assertFalse(self.service.file_exists('test-bucket', 'ghost.pdf'))

    def test_returns_false_on_no_such_object(self):
        self.client.stat_object.side_effect = _s3_error('NoSuchObject')

        self.assertFalse(self.service.file_exists('test-bucket', 'ghost.pdf'))

    def test_returns_false_on_no_such_bucket(self):
        self.client.stat_object.side_effect = _s3_error('NoSuchBucket')

        self.assertFalse(self.service.file_exists('ghost-bucket', 'file.pdf'))

    def test_returns_false_on_connection_failure(self):
        self.client.stat_object.side_effect = _max_retry_error()

        self.assertFalse(self.service.file_exists('test-bucket', 'file.pdf'))

    def test_passes_correct_bucket_and_object_to_sdk(self):
        self.client.stat_object.return_value = _stat()

        self.service.file_exists('my-bucket', 'docs/invoice.pdf')

        self.client.stat_object.assert_called_once_with('my-bucket', 'docs/invoice.pdf')


class TestMinioStorageServiceListFiles(_MinioServiceTestCase):

    # Success

    def test_returns_mapped_file_info_list(self):
        self.client.list_objects.return_value = iter([
            _minio_object('a.pdf', size=100),
            _minio_object('b.png', size=200),
        ])

        result = self.service.list_files('test-bucket')

        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], FileInfoSchema)
        names = [f.object_name for f in result]
        self.assertIn('a.pdf', names)
        self.assertIn('b.png', names)

    def test_excludes_directory_entries(self):
        self.client.list_objects.return_value = iter([
            _minio_object('folder/', is_dir=True),
            _minio_object('folder/file.pdf', is_dir=False),
        ])

        result = self.service.list_files('test-bucket')

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].object_name, 'folder/file.pdf')

    def test_returns_empty_list_when_bucket_is_empty(self):
        self.client.list_objects.return_value = iter([])

        result = self.service.list_files('test-bucket')

        self.assertEqual(result, [])

    def test_passes_prefix_to_sdk(self):
        self.client.list_objects.return_value = iter([])

        self.service.list_files('test-bucket', prefix='invoices/2024/')

        self.client.list_objects.assert_called_once_with(
            'test-bucket', prefix='invoices/2024/', recursive=True
        )

    def test_passes_recursive_false_to_sdk(self):
        self.client.list_objects.return_value = iter([])

        self.service.list_files('test-bucket', recursive=False)

        args, kwargs = self.client.list_objects.call_args
        self.assertFalse(kwargs['recursive'])

    def test_passes_none_prefix_when_empty_string(self):
        """Empty prefix string is converted to None for the SDK call."""
        self.client.list_objects.return_value = iter([])

        self.service.list_files('test-bucket', prefix='')

        args, kwargs = self.client.list_objects.call_args
        self.assertIsNone(kwargs['prefix'])

    # Failure

    def test_raises_not_found_on_no_such_bucket(self):
        self.client.list_objects.side_effect = _s3_error('NoSuchBucket')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.list_files('ghost-bucket')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_raises_server_error_on_other_s3_error(self):
        self.client.list_objects.side_effect = _s3_error('InternalError')

        with self.assertRaises(ServerException) as ctx:
            self.service.list_files('test-bucket')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)

    def test_raises_server_error_on_connection_failure(self):
        self.client.list_objects.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.list_files('test-bucket')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)


class TestMinioStorageServiceGetFileInfo(_MinioServiceTestCase):

    # Success

    def test_returns_file_info_schema_on_success(self):
        self.client.stat_object.return_value = _stat(
            size=2048,
            content_type='image/png',
            etag='img-etag',
        )

        result = self.service.get_file_info('test-bucket', 'images/photo.png')

        self.assertIsInstance(result, FileInfoSchema)
        self.assertEqual(result.bucket, 'test-bucket')
        self.assertEqual(result.object_name, 'images/photo.png')
        self.assertEqual(result.size, 2048)
        self.assertEqual(result.content_type, 'image/png')
        self.assertEqual(result.etag, 'img-etag')

    def test_maps_metadata_from_stat(self):
        self.client.stat_object.return_value = _stat(
            metadata={'x-amz-meta-author': 'admin'}
        )

        result = self.service.get_file_info('test-bucket', 'file.pdf')

        self.assertEqual(result.metadata, {'x-amz-meta-author': 'admin'})

    def test_passes_correct_bucket_and_object_to_sdk(self):
        self.client.stat_object.return_value = _stat()

        self.service.get_file_info('my-bucket', 'docs/contract.pdf')

        self.client.stat_object.assert_called_once_with('my-bucket', 'docs/contract.pdf')

    # Failure

    def test_raises_not_found_on_no_such_key(self):
        self.client.stat_object.side_effect = _s3_error('NoSuchKey')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.get_file_info('test-bucket', 'ghost.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_FILE_NOT_FOUND)

    def test_raises_not_found_on_no_such_object(self):
        self.client.stat_object.side_effect = _s3_error('NoSuchObject')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.get_file_info('test-bucket', 'ghost.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_FILE_NOT_FOUND)

    def test_raises_not_found_on_no_such_bucket(self):
        self.client.stat_object.side_effect = _s3_error('NoSuchBucket')

        with self.assertRaises(NotFoundException) as ctx:
            self.service.get_file_info('ghost-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_raises_server_error_on_other_s3_error(self):
        self.client.stat_object.side_effect = _s3_error('InternalError')

        with self.assertRaises(ServerException) as ctx:
            self.service.get_file_info('test-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)

    def test_raises_server_error_on_connection_failure(self):
        self.client.stat_object.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.get_file_info('test-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)


# ── Presigned URLs ─────────────────────────────────────────────────────────────

class TestMinioStorageServicePresignedUrls(_MinioServiceTestCase):

    def _schema(self, **overrides) -> PresignedUrlSchema:
        defaults = dict(
            bucket='test-bucket',
            object_name='docs/file.pdf',
            method=PresignedUrlMethod.GET,
            expires=timedelta(hours=1),
        )
        defaults.update(overrides)
        return PresignedUrlSchema(**defaults)

    # GET presigned URL

    def test_returns_get_url_on_success(self):
        self.client.presigned_get_object.return_value = 'https://minio/bucket/file?sig=abc'

        result = self.service.get_presigned_url(self._schema(method=PresignedUrlMethod.GET))

        self.assertEqual(result, 'https://minio/bucket/file?sig=abc')

    def test_calls_presigned_get_object_for_get_method(self):
        self.client.presigned_get_object.return_value = 'https://url'

        self.service.get_presigned_url(self._schema(method=PresignedUrlMethod.GET))

        self.client.presigned_get_object.assert_called_once()
        self.client.presigned_put_object.assert_not_called()

    def test_passes_bucket_and_object_to_get_sdk(self):
        self.client.presigned_get_object.return_value = 'https://url'

        self.service.get_presigned_url(
            self._schema(
                bucket='invoices',
                object_name='2024/inv-001.pdf',
                method=PresignedUrlMethod.GET,
            )
        )

        args, kwargs = self.client.presigned_get_object.call_args
        self.assertEqual(kwargs['bucket_name'], 'invoices')
        self.assertEqual(kwargs['object_name'], '2024/inv-001.pdf')

    def test_passes_expiry_to_get_sdk(self):
        self.client.presigned_get_object.return_value = 'https://url'
        expires = timedelta(minutes=15)

        self.service.get_presigned_url(
            self._schema(method=PresignedUrlMethod.GET, expires=expires)
        )

        args, kwargs = self.client.presigned_get_object.call_args
        self.assertEqual(kwargs['expires'], expires)

    # PUT presigned URL

    def test_returns_put_url_on_success(self):
        self.client.presigned_put_object.return_value = 'https://minio/bucket/new?sig=xyz'

        result = self.service.get_presigned_url(self._schema(method=PresignedUrlMethod.PUT))

        self.assertEqual(result, 'https://minio/bucket/new?sig=xyz')

    def test_calls_presigned_put_object_for_put_method(self):
        self.client.presigned_put_object.return_value = 'https://url'

        self.service.get_presigned_url(self._schema(method=PresignedUrlMethod.PUT))

        self.client.presigned_put_object.assert_called_once()
        self.client.presigned_get_object.assert_not_called()

    def test_passes_bucket_and_object_to_put_sdk(self):
        self.client.presigned_put_object.return_value = 'https://url'

        self.service.get_presigned_url(
            self._schema(
                bucket='uploads',
                object_name='new_file.pdf',
                method=PresignedUrlMethod.PUT,
            )
        )

        args, kwargs = self.client.presigned_put_object.call_args
        self.assertEqual(kwargs['bucket_name'], 'uploads')
        self.assertEqual(kwargs['object_name'], 'new_file.pdf')

    # Failure

    def test_raises_server_error_on_s3_error_for_get(self):
        self.client.presigned_get_object.side_effect = _s3_error('InternalError')

        with self.assertRaises(ServerException) as ctx:
            self.service.get_presigned_url(self._schema(method=PresignedUrlMethod.GET))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_PRESIGNED_URL_FAILED)

    def test_raises_server_error_on_s3_error_for_put(self):
        self.client.presigned_put_object.side_effect = _s3_error('AccessDenied')

        with self.assertRaises(ServerException) as ctx:
            self.service.get_presigned_url(self._schema(method=PresignedUrlMethod.PUT))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_PRESIGNED_URL_FAILED)

    def test_raises_server_error_on_connection_failure_for_get(self):
        self.client.presigned_get_object.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.get_presigned_url(self._schema(method=PresignedUrlMethod.GET))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)

    def test_raises_server_error_on_connection_failure_for_put(self):
        self.client.presigned_put_object.side_effect = _max_retry_error()

        with self.assertRaises(ServerException) as ctx:
            self.service.get_presigned_url(self._schema(method=PresignedUrlMethod.PUT))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_SERVICE_ERROR)
