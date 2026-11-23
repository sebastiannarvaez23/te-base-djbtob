"""Unit tests — políticas de cumplimiento (use cases + paths + draft flow)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.errors import AppErrorCode, NotFoundException, ServerException
from core.errors.codes import ERROR_REGISTRY
from core.signing import hash_content
from core.storage.domain.schemas import BucketSchema, FileInfoSchema
from platform.features.compliance.policy.policy.application.use_cases import (
    ApprovePolicyCountryDraftUseCase,
    CreatePolicyUseCase,
    DeletePolicyCountryUseCase,
    DeletePolicyUseCase,
    DiscardPolicyCountryDraftUseCase,
    GetPolicyByIdUseCase,
    GetPolicyCountryContentUseCase,
    ReleasePolicyCountryDraftUseCase,
    ReleasePolicyCountryVersionUseCase,
    SavePolicyCountryDraftUseCase,
    StartPolicyCountryDraftUseCase,
    UpdatePolicyUseCase,
)
from platform.features.compliance.policy.policy.domain.enums import PolicyAudience
from platform.features.compliance.policy.policy.domain.paths import (
    POLICY_BUCKET,
    policy_draft_object_key,
    policy_object_key,
)
from platform.features.compliance.policy.policy.domain.schemas import (
    CreatePolicySchema,
    PolicyCountrySummarySchema,
    PolicySchema,
    SavePolicyCountryDraftSchema,
    UpdatePolicySchema,
)

pytestmark = pytest.mark.unit


class FakeStorage:
    def __init__(self):
        self.files: dict[tuple[str, str], bytes] = {}
        self.buckets: set[str] = set()

    def create_bucket(self, data):
        self.buckets.add(data.bucket)
        return BucketSchema(name=data.bucket)

    def bucket_exists(self, bucket: str) -> bool:
        return bucket in self.buckets

    def ensure_bucket(self, data):
        self.buckets.add(data.bucket)
        return data

    def upload_file(self, data):
        self.files[(data.bucket, data.object_name)] = data.data
        return FileInfoSchema(
            bucket=data.bucket,
            object_name=data.object_name,
            size=len(data.data),
            content_type=data.content_type,
        )

    def replace_file(self, data):
        return self.upload_file(data)

    def download_file(self, bucket: str, object_name: str) -> bytes:
        key = (bucket, object_name)
        if key not in self.files:
            raise FileNotFoundError(object_name)
        return self.files[key]

    def delete_file(self, bucket: str, object_name: str) -> bool:
        self.files.pop((bucket, object_name), None)
        return True

    def file_exists(self, bucket: str, object_name: str) -> bool:
        return (bucket, object_name) in self.files


def _policy(**overrides) -> PolicySchema:
    base = dict(
        id=uuid4(),
        code='DATA-PROCESSING',
        name='Tratamiento de datos',
        audience=PolicyAudience.CLIENT,
        description='',
        is_active=True,
        countries=[],
        drafts=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return PolicySchema(**base)


def _country(**overrides) -> PolicyCountrySummarySchema:
    base = dict(
        id=uuid4(),
        country='CO',
        version=1,
        status='published',
        title='Tratamiento de datos',
        object_key='client/policies/DATA-PROCESSING/CO/v1.md',
        content_hash=hash_content('# Hola'),
        byte_size=6,
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return PolicyCountrySummarySchema(**base)


def _draft(**overrides) -> PolicyCountrySummarySchema:
    empty = b'# draft'
    base = dict(
        version=0,
        status='draft',
        object_key='client/policies/DATA-PROCESSING/CO/draft.md',
        content_hash=hash_content(empty),
        byte_size=len(empty),
    )
    base.update(overrides)
    return _country(**base)


class TestPolicyPaths:

    def test_client_and_admin_keys(self):
        assert policy_object_key('client', 'DATA-PROCESSING', 'CO', 1) == (
            'client/policies/DATA-PROCESSING/CO/v1.md'
        )
        assert policy_object_key(PolicyAudience.ADMIN, 'tos', 'US', 3) == (
            'admin/policies/TOS/US/v3.md'
        )
        assert policy_draft_object_key('client', 'DATA-PROCESSING', 'CO') == (
            'client/policies/DATA-PROCESSING/CO/draft.md'
        )


class TestPolicySchemas:

    def test_normalizes_code_and_rejects_invalid(self):
        ok = CreatePolicySchema(
            code='Data-Processing',
            name='X',
            audience=PolicyAudience.CLIENT,
        )
        assert ok.code == 'DATA-PROCESSING'
        with pytest.raises(ValidationError):
            CreatePolicySchema(code='Data Processing', name='X', audience=PolicyAudience.CLIENT)


class TestCreateAndUpdate:

    def test_create_rejects_duplicate_code(self):
        from core.errors import ConflictException

        repo = MagicMock()
        repo.get_by_code.return_value = _policy()
        with pytest.raises(ConflictException) as exc:
            CreatePolicyUseCase(repo).execute(
                CreatePolicySchema(
                    code='DATA-PROCESSING',
                    name='X',
                    audience=PolicyAudience.CLIENT,
                ),
            )
        assert exc.value.code == AppErrorCode.POLICY_DUPLICATE_CODE

    def test_create_ok(self):
        repo = MagicMock()
        repo.get_by_code.return_value = None
        created = _policy()
        repo.create.return_value = created
        result = CreatePolicyUseCase(repo).execute(
            CreatePolicySchema(
                code='PRIVACY',
                name='Privacidad',
                audience=PolicyAudience.ADMIN,
            ),
        )
        assert result.id == created.id

    def test_update_not_found(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException) as exc:
            UpdatePolicyUseCase(repo).execute(
                uuid4(), UpdatePolicySchema(name='Nuevo'),
            )
        assert exc.value.code == AppErrorCode.POLICY_NOT_FOUND

    def test_get_by_id_not_found(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            GetPolicyByIdUseCase(repo).execute(uuid4())


class TestDraftWorkflow:

    @patch('platform.features.geography.location.location.models.Country.objects')
    def test_start_draft_from_published(self, country_objects):
        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        published = _country()
        repo.get_by_id.return_value = policy
        repo.get_draft.return_value = None
        repo.get_country.return_value = published
        storage.files[(POLICY_BUCKET, published.object_key)] = b'# Hola'
        created = _draft(title=published.title, content_hash=hash_content(b'# Hola'), byte_size=6)
        repo.create_draft.return_value = created
        geo = MagicMock(id=uuid4(), is_active=True)
        country_objects.only.return_value.get.return_value = geo

        result = StartPolicyCountryDraftUseCase(repo, storage).execute(policy.id, 'CO')
        assert result.status.value == 'draft'
        assert result.markdown == '# Hola'
        draft_key = policy_draft_object_key(policy.audience, policy.code, 'CO')
        assert (POLICY_BUCKET, draft_key) in storage.files
        repo.create_draft.assert_called_once()
        assert repo.create_draft.call_args.kwargs.get('geo_country_id') == geo.id

    def test_start_reopens_existing_draft(self):
        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        draft = _draft(content_hash=hash_content(b'# draft'), byte_size=7)
        repo.get_by_id.return_value = policy
        repo.get_draft.return_value = draft
        storage.files[(POLICY_BUCKET, draft.object_key)] = b'# draft'

        result = StartPolicyCountryDraftUseCase(repo, storage).execute(policy.id, 'co')
        assert result.markdown == '# draft'
        repo.create_draft.assert_not_called()

    def test_save_draft_does_not_touch_published(self):
        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        draft = _draft()
        repo.get_by_id.return_value = policy
        repo.get_draft.return_value = draft
        updated = _draft(title='Nuevo', content_hash=hash_content(b'# x'), byte_size=3)
        repo.update_draft.return_value = updated

        result = SavePolicyCountryDraftUseCase(repo, storage).execute(
            policy.id,
            'CO',
            SavePolicyCountryDraftSchema(title='Nuevo', markdown='# x'),
        )
        assert result.title == 'Nuevo'
        repo.create_approved_version.assert_not_called()
        repo.release_approved_version.assert_not_called()
        assert (POLICY_BUCKET, draft.object_key) in storage.files

    def test_approve_creates_version_and_deletes_draft(self):
        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        markdown = b'# Oficial'
        draft = _draft(
            title='T',
            content_hash=hash_content(markdown),
            byte_size=len(markdown),
        )
        repo.get_by_id.return_value = policy
        repo.get_draft.return_value = draft
        repo.next_country_version.return_value = 2
        approved = _country(version=2, status='approved', title='T', content_hash=hash_content(markdown))
        repo.create_approved_version_and_drop_draft.return_value = (approved, draft)
        storage.files[(POLICY_BUCKET, draft.object_key)] = markdown

        result = ApprovePolicyCountryDraftUseCase(repo, storage).execute(policy.id, 'CO')
        assert result.version == 2
        assert result.status.value == 'approved'
        key = policy_object_key(policy.audience, policy.code, 'CO', 2)
        assert (POLICY_BUCKET, key) in storage.files
        assert (POLICY_BUCKET, draft.object_key) not in storage.files
        repo.create_approved_version_and_drop_draft.assert_called_once()
        repo.delete_draft.assert_not_called()

    def test_release_promotes_approved(self):
        repo = MagicMock()
        published = _country(version=2)
        repo.get_by_id.return_value = _policy()
        repo.release_approved_version.return_value = (published, 1)

        row, revoked = ReleasePolicyCountryVersionUseCase(repo).execute(uuid4(), 'CO')
        assert row.version == 2
        assert revoked == 1

    def test_orchestrator_approve_then_release(self):
        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        markdown = b'# Liberar'
        digest = hash_content(markdown)
        draft = _draft(title='T', content_hash=digest, byte_size=len(markdown))
        approved = _country(version=1, status='approved', title='T', content_hash=digest)
        published = _country(version=1, status='published', title='T', content_hash=digest)

        repo.get_by_id.return_value = policy
        repo.get_country.return_value = None
        repo.get_draft.return_value = draft
        repo.next_country_version.return_value = 1
        repo.create_approved_version_and_drop_draft.return_value = (approved, draft)
        repo.release_approved_version.return_value = (published, None)
        storage.files[(POLICY_BUCKET, draft.object_key)] = markdown

        result = ReleasePolicyCountryDraftUseCase(repo, storage).execute(policy.id, 'CO')
        assert result.created_new_version is True
        assert result.country.status.value == 'published'
        assert result.revoked_version is None
        repo.create_approved_version_and_drop_draft.assert_called_once()
        repo.release_approved_version.assert_called_once()
        # Primera liberación: change_summary vacío
        assert repo.create_approved_version_and_drop_draft.call_args.kwargs.get('change_summary') == ''

    def test_orchestrator_requires_change_summary_on_update(self):
        from core.errors import ValidationAppException

        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        markdown = b'# Update'
        digest = hash_content(markdown)
        draft = _draft(title='T', content_hash=digest, byte_size=len(markdown))
        prior = _country(version=1, status='published', title='Old')

        repo.get_by_id.return_value = policy
        repo.get_country.return_value = prior
        repo.get_draft.return_value = draft
        storage.files[(POLICY_BUCKET, draft.object_key)] = markdown

        with pytest.raises(ValidationAppException) as exc:
            ReleasePolicyCountryDraftUseCase(repo, storage).execute(policy.id, 'CO')
        assert exc.value.code == AppErrorCode.POLICY_CHANGE_SUMMARY_REQUIRED
        repo.create_approved_version.assert_not_called()
        repo.create_approved_version_and_drop_draft.assert_not_called()

    def test_orchestrator_update_with_change_summary(self):
        from platform.features.compliance.policy.policy.domain.schemas import (
            ReleasePolicyCountryDraftSchema,
        )

        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        markdown = b'# Update'
        digest = hash_content(markdown)
        draft = _draft(title='T', content_hash=digest, byte_size=len(markdown))
        approved = _country(
            version=2, status='approved', title='T', content_hash=digest,
            change_summary='Ajuste de cláusulas',
        )
        published = _country(
            version=2, status='published', title='T', content_hash=digest,
            change_summary='Ajuste de cláusulas',
        )
        prior = _country(version=1, status='published', title='Old')

        repo.get_by_id.return_value = policy
        repo.get_country.return_value = prior
        repo.get_draft.return_value = draft
        repo.next_country_version.return_value = 2
        repo.create_approved_version_and_drop_draft.return_value = (approved, draft)
        repo.release_approved_version.return_value = (published, 1)
        storage.files[(POLICY_BUCKET, draft.object_key)] = markdown

        result = ReleasePolicyCountryDraftUseCase(repo, storage).execute(
            policy.id,
            'CO',
            ReleasePolicyCountryDraftSchema(change_summary='Ajuste de cláusulas'),
        )
        assert result.revoked_version == 1
        assert repo.create_approved_version_and_drop_draft.call_args.kwargs['change_summary'] == (
            'Ajuste de cláusulas'
        )

    def test_discard_draft(self):
        repo = MagicMock()
        storage = FakeStorage()
        draft = _draft()
        repo.get_by_id.return_value = _policy()
        repo.delete_draft.return_value = draft
        storage.files[(POLICY_BUCKET, draft.object_key)] = b'x'

        DiscardPolicyCountryDraftUseCase(repo, storage).execute(uuid4(), 'CO')
        assert (POLICY_BUCKET, draft.object_key) not in storage.files

    def test_discard_missing_draft(self):
        repo = MagicMock()
        repo.get_by_id.return_value = _policy()
        repo.delete_draft.return_value = None
        with pytest.raises(NotFoundException) as exc:
            DiscardPolicyCountryDraftUseCase(repo, FakeStorage()).execute(uuid4(), 'CO')
        assert exc.value.code == AppErrorCode.POLICY_DRAFT_NOT_FOUND


class TestGetCountryContent:

    def test_downloads_published(self):
        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        loc = _country()
        repo.get_by_id.return_value = policy
        repo.get_country.return_value = loc
        body = '# Hola mundo'
        storage.files[(POLICY_BUCKET, loc.object_key)] = body.encode('utf-8')

        result = GetPolicyCountryContentUseCase(repo, storage).execute(policy.id, 'CO')
        assert result.markdown == body
        assert result.policy_code == policy.code

    def test_downloads_draft_when_requested(self):
        repo = MagicMock()
        storage = FakeStorage()
        policy = _policy()
        draft = _draft(content_hash=hash_content(b'# d'), byte_size=3)
        repo.get_by_id.return_value = policy
        repo.get_draft.return_value = draft
        storage.files[(POLICY_BUCKET, draft.object_key)] = b'# d'

        result = GetPolicyCountryContentUseCase(repo, storage).execute(
            policy.id, 'CO', status='draft',
        )
        assert result.status.value == 'draft'
        assert result.markdown == '# d'


class TestDelete:

    def test_delete_policy_cleans_storage(self):
        repo = MagicMock()
        storage = FakeStorage()
        pid = uuid4()
        key = 'client/policies/DATA-PROCESSING/CO/v1.md'
        storage.files[(POLICY_BUCKET, key)] = b'x'
        repo.list_country_object_keys.return_value = [key]
        repo.delete.return_value = True

        DeletePolicyUseCase(repo, storage).execute(pid)
        assert (POLICY_BUCKET, key) not in storage.files

    def test_delete_country(self):
        repo = MagicMock()
        storage = FakeStorage()
        loc = _country()
        repo.list_country_versions.return_value = [loc]
        repo.get_draft.return_value = None
        repo.delete_country.return_value = True
        storage.files[(POLICY_BUCKET, loc.object_key)] = b'x'

        DeletePolicyCountryUseCase(repo, storage).execute(uuid4(), 'CO')
        assert (POLICY_BUCKET, loc.object_key) not in storage.files


class TestErrorRegistry:

    def test_pol_codes_registered(self):
        for code in (
            AppErrorCode.POLICY_NOT_FOUND,
            AppErrorCode.POLICY_DRAFT_NOT_FOUND,
            AppErrorCode.POLICY_DRAFT_EXISTS,
            AppErrorCode.POLICY_NOT_APPROVED,
            AppErrorCode.POLICY_NOT_SIGNABLE,
            AppErrorCode.POLICY_COUNTRY_REVOKED,
        ):
            assert code in ERROR_REGISTRY
