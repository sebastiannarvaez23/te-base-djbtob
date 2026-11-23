"""
Unit tests for core/storage use cases.

All IStorageService calls are mocked — no MinIO connection required.
Each test class covers a single use case, with sub-sections for
success paths, failure paths, and delegation assertions.
"""
from datetime import timedelta
from unittest import TestCase
from unittest.mock import MagicMock, call

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ConflictException, NotFoundException
from core.storage.application.use_cases import (
    CreateBucketUseCase,
    DeleteBucketUseCase,
    DeleteFileUseCase,
    DownloadFileUseCase,
    EnsureBucketUseCase,
    GetFileInfoUseCase,
    GetPresignedUrlUseCase,
    ListBucketsUseCase,
    ListFilesUseCase,
    ReplaceFileUseCase,
    UploadFileUseCase,
)
from core.storage.domain.schemas import (
    BucketSchema,
    CreateBucketSchema,
    FileInfoSchema,
    PresignedUrlMethod,
    PresignedUrlSchema,
    ReplaceFileSchema,
    UploadFileSchema,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _bucket(**overrides) -> BucketSchema:
    defaults = dict(name='test-bucket')
    defaults.update(overrides)
    return BucketSchema(**defaults)


def _file_info(**overrides) -> FileInfoSchema:
    defaults = dict(
        bucket='test-bucket',
        object_name='folder/file.pdf',
        size=1024,
        content_type='application/pdf',
        etag='abc123',
    )
    defaults.update(overrides)
    return FileInfoSchema(**defaults)


def _upload_schema(**overrides) -> UploadFileSchema:
    defaults = dict(
        bucket='test-bucket',
        object_name='folder/file.pdf',
        data=b'PDF content',
        content_type='application/pdf',
    )
    defaults.update(overrides)
    return UploadFileSchema(**defaults)


def _replace_schema(**overrides) -> ReplaceFileSchema:
    defaults = dict(
        bucket='test-bucket',
        object_name='folder/file.pdf',
        data=b'New PDF content',
        content_type='application/pdf',
    )
    defaults.update(overrides)
    return ReplaceFileSchema(**defaults)


def _presigned_schema(**overrides) -> PresignedUrlSchema:
    defaults = dict(
        bucket='test-bucket',
        object_name='folder/file.pdf',
        method=PresignedUrlMethod.GET,
        expires=timedelta(hours=1),
    )
    defaults.update(overrides)
    return PresignedUrlSchema(**defaults)


# ── CreateBucketUseCase ────────────────────────────────────────────────────────

class TestCreateBucketUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = CreateBucketUseCase(self.service)

    # Success

    def test_creates_bucket_when_it_does_not_exist(self):
        self.service.bucket_exists.return_value = False
        expected = _bucket(name='invoices')
        self.service.create_bucket.return_value = expected

        result = self.uc.execute(CreateBucketSchema(bucket='invoices'))

        self.assertEqual(result, expected)

    def test_returns_bucket_schema_from_service(self):
        self.service.bucket_exists.return_value = False
        self.service.create_bucket.return_value = _bucket()

        result = self.uc.execute(CreateBucketSchema(bucket='test-bucket'))

        self.assertIsInstance(result, BucketSchema)

    # Failure

    def test_raises_conflict_when_bucket_already_exists(self):
        self.service.bucket_exists.return_value = True

        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(CreateBucketSchema(bucket='existing'))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_ALREADY_EXISTS)

    def test_conflict_detail_includes_bucket_name(self):
        self.service.bucket_exists.return_value = True

        with self.assertRaises(ConflictException) as ctx:
            self.uc.execute(CreateBucketSchema(bucket='my-bucket'))

        self.assertIn('my-bucket', ctx.exception.detail)

    # Delegation

    def test_checks_existence_before_creating(self):
        self.service.bucket_exists.return_value = False
        self.service.create_bucket.return_value = _bucket()

        self.uc.execute(CreateBucketSchema(bucket='test-bucket'))

        self.service.bucket_exists.assert_called_once_with('test-bucket')

    def test_does_not_call_create_when_already_exists(self):
        self.service.bucket_exists.return_value = True

        with self.assertRaises(ConflictException):
            self.uc.execute(CreateBucketSchema(bucket='test-bucket'))

        self.service.create_bucket.assert_not_called()

    def test_passes_schema_to_service(self):
        schema = CreateBucketSchema(bucket='new-bucket', region='us-east-1')
        self.service.bucket_exists.return_value = False
        self.service.create_bucket.return_value = _bucket(name='new-bucket')

        self.uc.execute(schema)

        self.service.create_bucket.assert_called_once_with(schema)


# ── EnsureBucketUseCase ────────────────────────────────────────────────────────

class TestEnsureBucketUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = EnsureBucketUseCase(self.service)

    # Success

    def test_creates_bucket_when_not_exists(self):
        self.service.bucket_exists.return_value = False
        self.service.create_bucket.return_value = _bucket()

        self.uc.execute('test-bucket')

        self.service.create_bucket.assert_called_once()

    def test_returns_bucket_schema_after_creation(self):
        self.service.bucket_exists.return_value = False
        self.service.create_bucket.return_value = _bucket(name='new')

        result = self.uc.execute('new')

        self.assertIsInstance(result, BucketSchema)
        self.assertEqual(result.name, 'new')

    def test_returns_bucket_schema_without_creating_when_exists(self):
        self.service.bucket_exists.return_value = True

        result = self.uc.execute('existing')

        self.service.create_bucket.assert_not_called()
        self.assertIsInstance(result, BucketSchema)
        self.assertEqual(result.name, 'existing')

    # Delegation

    def test_checks_bucket_existence(self):
        self.service.bucket_exists.return_value = True

        self.uc.execute('my-bucket')

        self.service.bucket_exists.assert_called_once_with('my-bucket')

    def test_passes_region_to_create_schema(self):
        self.service.bucket_exists.return_value = False
        self.service.create_bucket.return_value = _bucket()

        self.uc.execute('my-bucket', region='eu-west-1')

        schema = self.service.create_bucket.call_args[0][0]
        self.assertEqual(schema.region, 'eu-west-1')


# ── DeleteBucketUseCase ────────────────────────────────────────────────────────

class TestDeleteBucketUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = DeleteBucketUseCase(self.service)

    # Success

    def test_deletes_bucket_successfully(self):
        self.service.bucket_exists.return_value = True
        self.service.delete_bucket.return_value = True

        result = self.uc.execute('test-bucket')

        self.assertTrue(result)

    # Failure

    def test_raises_not_found_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('ghost-bucket')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_not_found_detail_includes_bucket_name(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('ghost-bucket')

        self.assertIn('ghost-bucket', ctx.exception.detail)

    # Delegation

    def test_does_not_call_delete_when_not_found(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException):
            self.uc.execute('ghost-bucket')

        self.service.delete_bucket.assert_not_called()

    def test_passes_bucket_name_to_service(self):
        self.service.bucket_exists.return_value = True
        self.service.delete_bucket.return_value = True

        self.uc.execute('my-bucket')

        self.service.delete_bucket.assert_called_once_with('my-bucket', force=False)

    def test_passes_force_flag_to_service(self):
        self.service.bucket_exists.return_value = True
        self.service.delete_bucket.return_value = True

        self.uc.execute('my-bucket', force=True)

        self.service.delete_bucket.assert_called_once_with('my-bucket', force=True)


# ── ListBucketsUseCase ─────────────────────────────────────────────────────────

class TestListBucketsUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = ListBucketsUseCase(self.service)

    # Success

    def test_returns_all_buckets(self):
        expected = [_bucket(name='a'), _bucket(name='b')]
        self.service.list_buckets.return_value = expected

        result = self.uc.execute()

        self.assertEqual(result, expected)

    def test_returns_empty_list_when_no_buckets(self):
        self.service.list_buckets.return_value = []

        result = self.uc.execute()

        self.assertEqual(result, [])

    # Delegation

    def test_delegates_to_service(self):
        self.service.list_buckets.return_value = []

        self.uc.execute()

        self.service.list_buckets.assert_called_once()


# ── UploadFileUseCase ──────────────────────────────────────────────────────────

class TestUploadFileUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = UploadFileUseCase(self.service)

    # Success

    def test_uploads_file_and_returns_file_info(self):
        self.service.bucket_exists.return_value = True
        expected = _file_info()
        self.service.upload_file.return_value = expected

        result = self.uc.execute(_upload_schema())

        self.assertEqual(result, expected)

    def test_creates_bucket_when_not_exists_then_uploads(self):
        self.service.bucket_exists.return_value = False
        self.service.create_bucket.return_value = _bucket()
        self.service.upload_file.return_value = _file_info()

        self.uc.execute(_upload_schema())

        self.service.create_bucket.assert_called_once()
        self.service.upload_file.assert_called_once()

    def test_skips_bucket_creation_when_already_exists(self):
        self.service.bucket_exists.return_value = True
        self.service.upload_file.return_value = _file_info()

        self.uc.execute(_upload_schema())

        self.service.create_bucket.assert_not_called()

    # Delegation

    def test_passes_schema_to_upload(self):
        schema = _upload_schema(object_name='reports/q1.csv', content_type='text/csv')
        self.service.bucket_exists.return_value = True
        self.service.upload_file.return_value = _file_info()

        self.uc.execute(schema)

        self.service.upload_file.assert_called_once_with(schema)

    def test_checks_bucket_existence_with_schema_bucket_name(self):
        schema = _upload_schema(bucket='invoices')
        self.service.bucket_exists.return_value = True
        self.service.upload_file.return_value = _file_info()

        self.uc.execute(schema)

        self.service.bucket_exists.assert_called_once_with('invoices')


# ── DownloadFileUseCase ────────────────────────────────────────────────────────

class TestDownloadFileUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = DownloadFileUseCase(self.service)

    # Success

    def test_downloads_file_and_returns_bytes(self):
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = True
        self.service.download_file.return_value = b'file content'

        result = self.uc.execute('test-bucket', 'folder/file.pdf')

        self.assertEqual(result, b'file content')

    # Failure

    def test_raises_not_found_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('ghost-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_raises_not_found_when_file_missing(self):
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('test-bucket', 'ghost.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_FILE_NOT_FOUND)

    def test_not_found_detail_includes_file_name(self):
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('test-bucket', 'ghost.pdf')

        self.assertIn('ghost.pdf', ctx.exception.detail)

    def test_does_not_download_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException):
            self.uc.execute('ghost-bucket', 'file.pdf')

        self.service.download_file.assert_not_called()

    # Delegation

    def test_passes_bucket_and_object_to_service(self):
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = True
        self.service.download_file.return_value = b''

        self.uc.execute('my-bucket', 'path/to/file.png')

        self.service.download_file.assert_called_once_with('my-bucket', 'path/to/file.png')


# ── DeleteFileUseCase ──────────────────────────────────────────────────────────

class TestDeleteFileUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = DeleteFileUseCase(self.service)

    # Success

    def test_deletes_file_and_returns_true(self):
        self.service.file_exists.return_value = True
        self.service.delete_file.return_value = True

        result = self.uc.execute('test-bucket', 'folder/file.pdf')

        self.assertTrue(result)

    # Failure

    def test_raises_not_found_when_file_missing(self):
        self.service.file_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('test-bucket', 'ghost.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_FILE_NOT_FOUND)

    def test_not_found_detail_includes_object_name(self):
        self.service.file_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('test-bucket', 'ghost.pdf')

        self.assertIn('ghost.pdf', ctx.exception.detail)

    def test_does_not_delete_when_file_missing(self):
        self.service.file_exists.return_value = False

        with self.assertRaises(NotFoundException):
            self.uc.execute('test-bucket', 'ghost.pdf')

        self.service.delete_file.assert_not_called()

    # Delegation

    def test_passes_bucket_and_object_to_service(self):
        self.service.file_exists.return_value = True
        self.service.delete_file.return_value = True

        self.uc.execute('my-bucket', 'path/doc.pdf')

        self.service.delete_file.assert_called_once_with('my-bucket', 'path/doc.pdf')

    def test_checks_file_existence_before_deleting(self):
        self.service.file_exists.return_value = True
        self.service.delete_file.return_value = True

        self.uc.execute('my-bucket', 'path/doc.pdf')

        self.service.file_exists.assert_called_once_with('my-bucket', 'path/doc.pdf')


# ── ReplaceFileUseCase ─────────────────────────────────────────────────────────

class TestReplaceFileUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = ReplaceFileUseCase(self.service)

    # Success

    def test_replaces_file_and_returns_file_info(self):
        self.service.bucket_exists.return_value = True
        expected = _file_info(etag='new-etag')
        self.service.replace_file.return_value = expected

        result = self.uc.execute(_replace_schema())

        self.assertEqual(result, expected)

    def test_creates_bucket_when_not_exists(self):
        self.service.bucket_exists.return_value = False
        self.service.create_bucket.return_value = _bucket()
        self.service.replace_file.return_value = _file_info()

        self.uc.execute(_replace_schema())

        self.service.create_bucket.assert_called_once()

    def test_skips_bucket_creation_when_already_exists(self):
        self.service.bucket_exists.return_value = True
        self.service.replace_file.return_value = _file_info()

        self.uc.execute(_replace_schema())

        self.service.create_bucket.assert_not_called()

    # Delegation

    def test_passes_schema_to_service(self):
        schema = _replace_schema(object_name='docs/contract.pdf')
        self.service.bucket_exists.return_value = True
        self.service.replace_file.return_value = _file_info()

        self.uc.execute(schema)

        self.service.replace_file.assert_called_once_with(schema)


# ── GetFileInfoUseCase ─────────────────────────────────────────────────────────

class TestGetFileInfoUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = GetFileInfoUseCase(self.service)

    # Success

    def test_returns_file_info_when_found(self):
        self.service.bucket_exists.return_value = True
        expected = _file_info(size=4096, etag='xyz')
        self.service.get_file_info.return_value = expected

        result = self.uc.execute('test-bucket', 'folder/file.pdf')

        self.assertEqual(result, expected)

    # Failure

    def test_raises_not_found_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('ghost-bucket', 'file.pdf')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_does_not_call_service_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException):
            self.uc.execute('ghost-bucket', 'file.pdf')

        self.service.get_file_info.assert_not_called()

    # Delegation

    def test_passes_bucket_and_object_to_service(self):
        self.service.bucket_exists.return_value = True
        self.service.get_file_info.return_value = _file_info()

        self.uc.execute('my-bucket', 'path/to/doc.pdf')

        self.service.get_file_info.assert_called_once_with('my-bucket', 'path/to/doc.pdf')


# ── ListFilesUseCase ───────────────────────────────────────────────────────────

class TestListFilesUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = ListFilesUseCase(self.service)

    # Success

    def test_returns_list_of_file_infos(self):
        expected = [_file_info(object_name='a.pdf'), _file_info(object_name='b.pdf')]
        self.service.bucket_exists.return_value = True
        self.service.list_files.return_value = expected

        result = self.uc.execute('test-bucket')

        self.assertEqual(result, expected)

    def test_returns_empty_list_when_bucket_is_empty(self):
        self.service.bucket_exists.return_value = True
        self.service.list_files.return_value = []

        result = self.uc.execute('test-bucket')

        self.assertEqual(result, [])

    # Failure

    def test_raises_not_found_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute('ghost-bucket')

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_does_not_list_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException):
            self.uc.execute('ghost-bucket')

        self.service.list_files.assert_not_called()

    # Delegation

    def test_passes_prefix_to_service(self):
        self.service.bucket_exists.return_value = True
        self.service.list_files.return_value = []

        self.uc.execute('my-bucket', prefix='invoices/2024/')

        self.service.list_files.assert_called_once_with(
            'my-bucket', prefix='invoices/2024/', recursive=True, max_keys=None,
        )

    def test_passes_recursive_flag_to_service(self):
        self.service.bucket_exists.return_value = True
        self.service.list_files.return_value = []

        self.uc.execute('my-bucket', recursive=False)

        self.service.list_files.assert_called_once_with(
            'my-bucket', prefix='', recursive=False, max_keys=None,
        )

    def test_defaults_to_empty_prefix_and_recursive_true(self):
        self.service.bucket_exists.return_value = True
        self.service.list_files.return_value = []

        self.uc.execute('my-bucket')

        self.service.list_files.assert_called_once_with(
            'my-bucket', prefix='', recursive=True, max_keys=None,
        )

    def test_passes_max_keys_to_service(self):
        self.service.bucket_exists.return_value = True
        self.service.list_files.return_value = []

        self.uc.execute('my-bucket', max_keys=50)

        self.service.list_files.assert_called_once_with(
            'my-bucket', prefix='', recursive=True, max_keys=50,
        )


# ── GetPresignedUrlUseCase ─────────────────────────────────────────────────────

class TestGetPresignedUrlUseCase(TestCase):

    def setUp(self):
        self.service = MagicMock()
        self.uc = GetPresignedUrlUseCase(self.service)

    # Success

    def test_returns_presigned_url_for_get(self):
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = True
        self.service.get_presigned_url.return_value = 'https://minio/test-bucket/file.pdf?sig=abc'

        result = self.uc.execute(_presigned_schema(method=PresignedUrlMethod.GET))

        self.assertEqual(result, 'https://minio/test-bucket/file.pdf?sig=abc')

    def test_returns_presigned_url_for_put(self):
        self.service.bucket_exists.return_value = True
        self.service.get_presigned_url.return_value = 'https://minio/test-bucket/upload?sig=xyz'

        result = self.uc.execute(_presigned_schema(method=PresignedUrlMethod.PUT))

        self.assertEqual(result, 'https://minio/test-bucket/upload?sig=xyz')

    def test_skips_file_existence_check_for_put(self):
        """PUT is for uploading a new file; it must not require the file to exist."""
        self.service.bucket_exists.return_value = True
        self.service.get_presigned_url.return_value = 'https://minio/url'

        self.uc.execute(_presigned_schema(method=PresignedUrlMethod.PUT))

        self.service.file_exists.assert_not_called()

    # Failure

    def test_raises_not_found_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(_presigned_schema())

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_BUCKET_NOT_FOUND)

    def test_raises_not_found_when_file_missing_for_get(self):
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = False

        with self.assertRaises(NotFoundException) as ctx:
            self.uc.execute(_presigned_schema(method=PresignedUrlMethod.GET))

        self.assertEqual(ctx.exception.code, AppErrorCode.STR_FILE_NOT_FOUND)

    def test_does_not_generate_url_when_bucket_missing(self):
        self.service.bucket_exists.return_value = False

        with self.assertRaises(NotFoundException):
            self.uc.execute(_presigned_schema())

        self.service.get_presigned_url.assert_not_called()

    def test_does_not_generate_url_when_file_missing_for_get(self):
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = False

        with self.assertRaises(NotFoundException):
            self.uc.execute(_presigned_schema(method=PresignedUrlMethod.GET))

        self.service.get_presigned_url.assert_not_called()

    # Delegation

    def test_passes_schema_to_service(self):
        schema = _presigned_schema(
            bucket='docs',
            object_name='contract.pdf',
            method=PresignedUrlMethod.GET,
            expires=timedelta(minutes=30),
        )
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = True
        self.service.get_presigned_url.return_value = 'https://url'

        self.uc.execute(schema)

        self.service.get_presigned_url.assert_called_once_with(schema)

    def test_checks_bucket_existence_with_correct_name(self):
        self.service.bucket_exists.return_value = True
        self.service.file_exists.return_value = True
        self.service.get_presigned_url.return_value = 'https://url'

        self.uc.execute(_presigned_schema(bucket='invoices'))

        self.service.bucket_exists.assert_called_once_with('invoices')
