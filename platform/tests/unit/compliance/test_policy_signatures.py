"""Unit tests — firma digital de políticas."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    PermissionException,
)
from core.errors.codes import ERROR_REGISTRY
from core.signing import hash_content
from core.storage.domain.schemas import FileInfoSchema, BucketSchema
from platform.features.compliance.policy.policy.application.sign_use_cases import (
    ListPendingPoliciesUseCase,
    SignPolicyUseCase,
    VerifyPolicySignatureUseCase,
)
from platform.features.compliance.policy.policy.domain.enums import PolicyAudience, PolicySubjectType
from platform.features.compliance.policy.policy.domain.paths import POLICY_BUCKET
from platform.features.compliance.policy.policy.domain.schemas import (
    PendingPolicySchema,
    PolicyCountrySummarySchema,
    PolicySchema,
    PolicySignatureSchema,
    SignPolicyContextSchema,
    SignPolicySchema,
    SignatoryRef,
)

pytestmark = pytest.mark.unit

MARKDOWN = '# Política de plataforma\n\nAcepto.'
CONTENT_HASH = hash_content(MARKDOWN.encode('utf-8'))


class FakeStorage:
    def __init__(self):
        self.files: dict[tuple[str, str], bytes] = {}
        self.buckets: set[str] = set()

    def create_bucket(self, data):
        self.buckets.add(data.bucket)
        return BucketSchema(name=data.bucket)

    def bucket_exists(self, bucket: str) -> bool:
        return bucket in self.buckets

    def upload_file(self, data):
        self.files[(data.bucket, data.object_name)] = data.data
        return FileInfoSchema(
            bucket=data.bucket, object_name=data.object_name, size=len(data.data),
        )

    def download_file(self, bucket: str, object_name: str) -> bytes:
        return self.files[(bucket, object_name)]

    def file_exists(self, bucket: str, object_name: str) -> bool:
        return (bucket, object_name) in self.files


def _policy(**overrides) -> PolicySchema:
    base = dict(
        id=uuid4(),
        code='PLATFORM-TOS',
        name='Términos plataforma',
        audience=PolicyAudience.ADMIN,
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
        title='Términos',
        object_key='admin/policies/PLATFORM-TOS/CO/v1.md',
        content_hash=CONTENT_HASH,
        byte_size=len(MARKDOWN.encode('utf-8')),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return PolicyCountrySummarySchema(**base)


def _signatory(**overrides) -> SignatoryRef:
    base = dict(
        subject_type=PolicySubjectType.ADMIN,
        subject_id=str(uuid4()),
        tenant_id=None,
    )
    base.update(overrides)
    return SignatoryRef(**base)


def _signature(**overrides) -> PolicySignatureSchema:
    from core.signing import DocumentBinding, SignatoryContext, seal_signature

    loc_id = overrides.get('policy_country_id', uuid4())
    subject = overrides.get('subject_id', str(uuid4()))
    signed_at = overrides.get('signed_at', datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc))
    evidence = seal_signature(
        DocumentBinding(
            document_type=overrides.get('policy_code', 'PLATFORM-TOS'),
            document_version_id=str(loc_id),
            content_hash=overrides.get('content_hash', CONTENT_HASH),
        ),
        SignatoryContext(
            subject_id=subject,
            signed_at=signed_at,
            channel='web',
        ),
        secret='unit-test-signing-secret',
    )
    base = dict(
        id=uuid4(),
        policy_id=uuid4(),
        policy_code='PLATFORM-TOS',
        policy_country_id=loc_id,
        country='CO',
        content_hash=CONTENT_HASH,
        subject_type=PolicySubjectType.ADMIN,
        subject_id=subject,
        tenant_id=None,
        signed_at=signed_at,
        seal=evidence.seal,
        seal_algorithm=evidence.seal_algorithm,
        canonical_payload=evidence.canonical_payload,
        ip_address=None,
        user_agent=None,
        request_id=None,
        channel='web',
    )
    base.update(overrides)
    return PolicySignatureSchema(**base)


class TestSignPolicyUseCase:

    def test_signs_active_admin_policy(self, monkeypatch):
        monkeypatch.setenv('SIGNING_SECRET_KEY', 'unit-test-signing-secret')
        from django.test import override_settings

        policy = _policy()
        loc = _country()
        policies = MagicMock()
        policies.get_by_id.return_value = policy
        policies.get_country.return_value = loc
        signatures = MagicMock()
        signatures.find_for_version.return_value = None
        signatures.create.side_effect = lambda data: data
        storage = FakeStorage()
        storage.files[(POLICY_BUCKET, loc.object_key)] = MARKDOWN.encode('utf-8')

        with override_settings(SIGNING_SECRET_KEY='unit-test-signing-secret'):
            result = SignPolicyUseCase(policies, signatures, storage).execute(
                SignPolicySchema(
                    policy_id=policy.id,
                    country='CO',
                    signatory=_signatory(),
                    context=SignPolicyContextSchema(channel='web'),
                ),
            )

        assert result.seal
        assert result.content_hash == CONTENT_HASH
        assert result.policy_code == policy.code
        signatures.create.assert_called_once()

    def test_rejects_audience_mismatch(self):
        policies = MagicMock()
        policies.get_by_id.return_value = _policy(audience=PolicyAudience.CLIENT)
        with pytest.raises(PermissionException) as exc:
            SignPolicyUseCase(policies, MagicMock(), FakeStorage()).execute(
                SignPolicySchema(
                    policy_id=uuid4(),
                    country='CO',
                    signatory=_signatory(subject_type=PolicySubjectType.ADMIN),
                ),
            )
        assert exc.value.code == AppErrorCode.POLICY_AUDIENCE_MISMATCH

    def test_rejects_inactive(self):
        policies = MagicMock()
        policies.get_by_id.return_value = _policy(is_active=False)
        with pytest.raises(ConflictException) as exc:
            SignPolicyUseCase(policies, MagicMock(), FakeStorage()).execute(
                SignPolicySchema(
                    policy_id=uuid4(),
                    country='CO',
                    signatory=_signatory(),
                ),
            )
        assert exc.value.code == AppErrorCode.POLICY_INACTIVE

    def test_rejects_already_signed(self):
        policies = MagicMock()
        policies.get_by_id.return_value = _policy()
        policies.get_country.return_value = _country()
        signatures = MagicMock()
        signatures.find_for_version.return_value = _signature()
        with pytest.raises(ConflictException) as exc:
            SignPolicyUseCase(policies, signatures, FakeStorage()).execute(
                SignPolicySchema(
                    policy_id=uuid4(),
                    country='CO',
                    signatory=_signatory(),
                ),
            )
        assert exc.value.code == AppErrorCode.POLICY_ALREADY_SIGNED

    def test_rejects_tampered_content(self):
        policies = MagicMock()
        policies.get_by_id.return_value = _policy()
        loc = _country()
        policies.get_country.return_value = loc
        signatures = MagicMock()
        signatures.find_for_version.return_value = None
        storage = FakeStorage()
        storage.files[(POLICY_BUCKET, loc.object_key)] = b'# contenido alterado'

        with pytest.raises(ConflictException) as exc:
            SignPolicyUseCase(policies, signatures, storage).execute(
                SignPolicySchema(
                    policy_id=uuid4(),
                    country='CO',
                    signatory=_signatory(),
                ),
            )
        assert exc.value.code == AppErrorCode.POLICY_CONTENT_TAMPERED

    def test_policy_not_found(self):
        policies = MagicMock()
        policies.get_by_id.return_value = None
        with pytest.raises(NotFoundException):
            SignPolicyUseCase(policies, MagicMock(), FakeStorage()).execute(
                SignPolicySchema(
                    policy_id=uuid4(),
                    country='CO',
                    signatory=_signatory(),
                ),
            )


class TestPendingAndVerify:

    def test_list_pending_delegates(self):
        signatures = MagicMock()
        pending = [
            PendingPolicySchema(
                policy_id=uuid4(),
                code='PLATFORM-TOS',
                name='TOS',
                audience=PolicyAudience.ADMIN,
                country='CO',
                version=1,
                title='TOS',
                content_hash=CONTENT_HASH,
                policy_country_id=uuid4(),
            ),
        ]
        signatures.list_pending_for_subject.return_value = pending
        result = ListPendingPoliciesUseCase(signatures).execute(
            subject=_signatory(), country='CO',
        )
        assert len(result) == 1
        kwargs = signatures.list_pending_for_subject.call_args.kwargs
        assert kwargs['country'] == 'CO'
        assert kwargs['policy_codes'] is None

    def test_list_pending_forwards_required_codes(self):
        signatures = MagicMock()
        signatures.list_pending_for_subject.return_value = []
        subject = _signatory()
        ListPendingPoliciesUseCase(signatures).execute(
            subject=subject,
            country='co',
            policy_codes=('PRIVACY-POLICY', 'DATA-PROCESSING'),
        )
        kwargs = signatures.list_pending_for_subject.call_args.kwargs
        assert kwargs['country'] == 'CO'
        assert kwargs['policy_codes'] == ('PRIVACY-POLICY', 'DATA-PROCESSING')

    def test_verify_valid_signature(self, monkeypatch):
        from django.test import override_settings

        row = _signature()
        signatures = MagicMock()
        signatures.get_by_id.return_value = row
        with override_settings(SIGNING_SECRET_KEY='unit-test-signing-secret'):
            check = VerifyPolicySignatureUseCase(signatures).execute(row.id)
        assert check.valid is True

    def test_verify_detects_tampered_seal(self):
        from django.test import override_settings

        row = _signature(seal='ab' * 32)
        signatures = MagicMock()
        signatures.get_by_id.return_value = row
        with override_settings(SIGNING_SECRET_KEY='unit-test-signing-secret'):
            check = VerifyPolicySignatureUseCase(signatures).execute(row.id)
        assert check.valid is False
        assert check.reason == 'seal_mismatch'


class TestSignErrorCodes:

    def test_new_pol_codes_registered(self):
        for code in (
            AppErrorCode.POLICY_ALREADY_SIGNED,
            AppErrorCode.POLICY_INACTIVE,
            AppErrorCode.POLICY_AUDIENCE_MISMATCH,
            AppErrorCode.POLICY_SIGNATURE_NOT_FOUND,
            AppErrorCode.POLICY_CONTENT_TAMPERED,
            AppErrorCode.POLICY_SIGNATURE_INVALID,
            AppErrorCode.POLICY_HAS_SIGNATURES,
        ):
            assert code in ERROR_REGISTRY
