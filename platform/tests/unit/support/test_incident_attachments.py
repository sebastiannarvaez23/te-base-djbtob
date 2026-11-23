"""Unit tests de adjuntos de incidencias: política de medios, subida, firma y purga."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from core.errors.codes import AppErrorCode
from core.errors.exceptions import AppException
from platform.features.support.incidents.incident.application.attachments import (
    AttachIncidentMediaUseCase,
    SignIncidentAttachmentsUseCase,
)
from platform.features.support.incidents.incident.application.purge_incidents import (
    PurgeIncidentsUseCase,
)
from platform.features.support.incidents.incident.domain.attachment_policy import (
    MAX_IMAGE_BYTES,
    classify_media,
    sanitize_name,
)
from platform.features.support.incidents.incident.domain.interfaces import (
    AttachmentLimitExceeded,
    IIncidentAttachmentRepository,
    IIncidentAttachmentStorage,
    IIncidentRepository,
)
from platform.features.support.incidents.incident.domain.schemas import (
    AttachmentUpload,
    IncidentAttachment,
    IncidentView,
)

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 32
GIF = b'GIF89a' + b'\x00' * 32
WEBP = b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 32
MP4 = b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 32

NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
INCIDENT_ID = '01923456-7890-7abc-8def-0123456789ab'


def _incident(**overrides):
    data = dict(
        id=INCIDENT_ID, code='INC-2026-0001', status='open', severity='low',
        kind='suggestion', schema_name='acme', reporter_user_id='u1',
        reported_at=(NOW - timedelta(minutes=2)).isoformat(),
    )
    data.update(overrides)
    return IncidentView(**data)


def _stored(n):
    return IncidentAttachment(
        id=f'a{n}', object_name=f'admin/support/incidents/x/a{n}.png', name=f'a{n}.png',
        content_type='image/png', size=10, kind='image', uploaded_at=NOW.isoformat(),
    )


class _FakeAttachmentRepo(IIncidentAttachmentRepository):
    def __init__(self, incident=None, *, fail=None):
        self.incident = incident
        self.fail = fail
        self.appended = []

    def get(self, incident_id):
        return self.incident if self.incident and self.incident.id == incident_id else None

    def append_attachments(self, incident_id, items, *, max_total):
        if self.fail:
            raise self.fail
        if self.incident is None:
            return None
        if len(self.incident.attachments) + len(items) > max_total:
            raise AttachmentLimitExceeded()
        self.appended.extend(items)
        self.incident = self.incident.model_copy(
            update={'attachments': self.incident.attachments + list(items)},
        )
        return self.incident

    def attachment_objects_for_purge(self, before, statuses):
        return ['admin/support/incidents/x/old.png']


class _FakeStorage(IIncidentAttachmentStorage):
    def __init__(self, *, fail_put_after=None, fail_sign=False):
        self.objects = {}
        self.deleted = []
        self.fail_put_after = fail_put_after
        self.fail_sign = fail_sign

    def put(self, object_name, data, content_type):
        if self.fail_put_after is not None and len(self.objects) >= self.fail_put_after:
            raise RuntimeError('minio down')
        self.objects[object_name] = (data, content_type)

    def delete(self, object_name):
        self.deleted.append(object_name)
        self.objects.pop(object_name, None)

    def signed_url(self, object_name):
        if self.fail_sign:
            raise RuntimeError('cannot sign')
        return f'https://minio.local/{object_name}?sig=1'


def _uc(repo, storage, window_minutes=15):
    return AttachIncidentMediaUseCase(
        repo, storage, window=timedelta(minutes=window_minutes), clock=lambda: NOW,
    )


def _run(uc, files, **kw):
    params = dict(incident_id=INCIDENT_ID, reporter_user_id='u1', schema_name='acme', files=files)
    params.update(kw)
    return uc.execute(**params)


class AttachmentPolicyTests(TestCase):

    def test_accepts_supported_media(self):
        cases = [
            ('a.png', 'image/png', PNG, 'image'),
            ('a.JPG', 'image/jpeg', JPG, 'image'),
            ('a.gif', 'image/gif', GIF, 'gif'),
            ('a.webp', '', WEBP, 'image'),
            ('a.mp4', 'video/mp4', MP4, 'video'),
        ]
        for name, mime, data, kind in cases:
            media = classify_media(name, mime, data)
            self.assertIsNotNone(media, name)
            self.assertEqual(media.kind, kind)

    def test_rejects_spoofed_signature(self):
        self.assertIsNone(classify_media('a.png', 'image/png', JPG))

    def test_rejects_mime_mismatch(self):
        self.assertIsNone(classify_media('a.png', 'image/jpeg', PNG))

    def test_rejects_blocked_and_double_extensions(self):
        self.assertIsNone(classify_media('a.svg', 'image/svg+xml', b'<svg/>'))
        self.assertIsNone(classify_media('a.exe.png', 'image/png', PNG))

    def test_rejects_unsupported_empty_and_oversized(self):
        self.assertIsNone(classify_media('a.pdf', 'application/pdf', b'%PDF-1.7'))
        self.assertIsNone(classify_media('a.png', 'image/png', b''))
        self.assertIsNone(classify_media('noext', 'image/png', PNG))
        too_big = PNG + b'\x00' * MAX_IMAGE_BYTES
        self.assertIsNone(classify_media('a.png', 'image/png', too_big))

    def test_sanitize_name_strips_paths_and_controls(self):
        self.assertEqual(sanitize_name('..\\..\\evil<1>.png'), 'evil_1_.png')
        self.assertEqual(sanitize_name('   '), 'evidence')


class AttachIncidentMediaUseCaseTests(TestCase):

    def test_stores_files_and_records_metadata(self):
        repo, storage = _FakeAttachmentRepo(_incident()), _FakeStorage()
        result = _run(_uc(repo, storage), [
            AttachmentUpload(name='pantalla.png', content_type='image/png', data=PNG),
            AttachmentUpload(name='flujo.mp4', content_type='video/mp4', data=MP4),
        ])
        self.assertEqual(len(result.attachments), 2)
        self.assertEqual(len(storage.objects), 2)
        first = result.attachments[0]
        self.assertTrue(first.object_name.startswith(f'admin/support/incidents/{INCIDENT_ID}/'))
        self.assertTrue(first.object_name.endswith('.png'))
        self.assertEqual(first.name, 'pantalla.png')
        self.assertEqual(result.attachments[1].kind, 'video')

    def test_foreign_reporter_gets_not_found(self):
        repo, storage = _FakeAttachmentRepo(_incident()), _FakeStorage()
        files = [AttachmentUpload(name='a.png', content_type='image/png', data=PNG)]
        for kw in ({'reporter_user_id': 'other'}, {'schema_name': 'other'}, {'incident_id': 'nope'}):
            with self.assertRaises(AppException) as ctx:
                _run(_uc(repo, storage), files, **kw)
            self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_NOT_FOUND)
        self.assertEqual(storage.objects, {})

    def test_window_closed(self):
        old = _incident(reported_at=(NOW - timedelta(hours=1)).isoformat())
        storage = _FakeStorage()
        with self.assertRaises(AppException) as ctx:
            _run(_uc(_FakeAttachmentRepo(old), storage),
                 [AttachmentUpload(name='a.png', content_type='image/png', data=PNG)])
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_ATTACHMENTS_CLOSED)
        self.assertEqual(storage.objects, {})

    def test_limit_counts_existing_attachments(self):
        incident = _incident(attachments=[_stored(i) for i in range(4)])
        storage = _FakeStorage()
        files = [AttachmentUpload(name=f'{i}.png', content_type='image/png', data=PNG) for i in range(2)]
        with self.assertRaises(AppException) as ctx:
            _run(_uc(_FakeAttachmentRepo(incident), storage), files)
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_ATTACHMENTS_LIMIT)
        self.assertEqual(storage.objects, {})

    def test_rejects_empty_and_too_many_files(self):
        uc = _uc(_FakeAttachmentRepo(_incident()), _FakeStorage())
        with self.assertRaises(AppException) as ctx:
            _run(uc, [])
        self.assertEqual(ctx.exception.code, AppErrorCode.VALIDATION_ERROR)
        files = [AttachmentUpload(name=f'{i}.png', content_type='image/png', data=PNG) for i in range(6)]
        with self.assertRaises(AppException) as ctx:
            _run(uc, files)
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_ATTACHMENTS_LIMIT)

    def test_invalid_file_rejects_whole_batch_before_upload(self):
        storage = _FakeStorage()
        files = [
            AttachmentUpload(name='ok.png', content_type='image/png', data=PNG),
            AttachmentUpload(name='fake.png', content_type='image/png', data=b'<script>'),
        ]
        with self.assertRaises(AppException) as ctx:
            _run(_uc(_FakeAttachmentRepo(_incident()), storage), files)
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_ATTACHMENT_INVALID)
        self.assertEqual(storage.objects, {})

    def test_storage_failure_rolls_back_uploaded_objects(self):
        repo, storage = _FakeAttachmentRepo(_incident()), _FakeStorage(fail_put_after=1)
        files = [AttachmentUpload(name=f'{i}.png', content_type='image/png', data=PNG) for i in range(2)]
        with self.assertRaises(AppException) as ctx:
            _run(_uc(repo, storage), files)
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_ATTACHMENT_STORAGE)
        self.assertEqual(storage.objects, {})
        self.assertEqual(len(storage.deleted), 1)
        self.assertEqual(repo.appended, [])

    def test_concurrent_limit_in_repository_rolls_back(self):
        repo = _FakeAttachmentRepo(_incident(), fail=AttachmentLimitExceeded())
        storage = _FakeStorage()
        with self.assertRaises(AppException) as ctx:
            _run(_uc(repo, storage), [AttachmentUpload(name='a.png', content_type='image/png', data=PNG)])
        self.assertEqual(ctx.exception.code, AppErrorCode.INCIDENT_ATTACHMENTS_LIMIT)
        self.assertEqual(storage.objects, {})


class SignIncidentAttachmentsUseCaseTests(TestCase):

    def test_signs_without_exposing_object_name(self):
        views = SignIncidentAttachmentsUseCase(_FakeStorage()).execute(
            _incident(attachments=[_stored(1)]),
        )
        self.assertEqual(len(views), 1)
        self.assertIn('sig=1', views[0].url)
        self.assertNotIn('object_name', views[0].model_dump())

    def test_sign_failure_degrades_to_empty_url(self):
        views = SignIncidentAttachmentsUseCase(_FakeStorage(fail_sign=True)).execute(
            _incident(attachments=[_stored(1)]),
        )
        self.assertEqual(views[0].url, '')


class _PurgeRepo(IIncidentRepository):
    def __init__(self):
        self.purged = False

    def create(self, data):  # pragma: no cover
        raise NotImplementedError

    def get_by_token(self, token):  # pragma: no cover
        return None

    def get(self, incident_id):  # pragma: no cover
        return None

    def list(self, filters, limit=50, offset=0):  # pragma: no cover
        return []

    def count(self, filters):  # pragma: no cover
        return 0

    def update_status(self, incident_id, **kw):  # pragma: no cover
        return None

    def purge(self, before, statuses):
        self.purged = True
        return 3


class PurgeIncidentAttachmentsTests(TestCase):

    def test_purge_deletes_attachment_objects(self):
        repo, storage = _PurgeRepo(), _FakeStorage()
        deleted = PurgeIncidentsUseCase(
            repo, attachments=_FakeAttachmentRepo(), storage=storage,
        ).execute(30)
        self.assertEqual(deleted, 3)
        self.assertTrue(repo.purged)
        self.assertEqual(storage.deleted, ['admin/support/incidents/x/old.png'])

    def test_purge_without_storage_keeps_previous_behaviour(self):
        repo = _PurgeRepo()
        self.assertEqual(PurgeIncidentsUseCase(repo).execute(30), 3)
