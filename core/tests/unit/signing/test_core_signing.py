"""Unit tests para core/signing (firma digital genérica)."""

from datetime import datetime, timezone

import pytest
from django.test import override_settings
from pydantic import ValidationError

from core.errors import AppErrorCode, ServerException, ValidationAppException
from core.errors.codes import ERROR_REGISTRY
from core.signing import (
    SEAL_ALGORITHM_V1,
    DocumentBinding,
    SignatoryContext,
    DigitalSignatureService,
    get_signature_service,
    hash_content,
    seal_signature,
    verify_signature,
)
from core.signing.canonical import canonical_payload, normalize_utc


SECRET = 'unit-test-signing-secret'


def _document(content: str = 'Política de privacidad v1') -> DocumentBinding:
    return DocumentBinding(
        document_type='privacy',
        document_version_id='ver-001',
        content_hash=hash_content(content),
    )


def _signatory(**overrides) -> SignatoryContext:
    base = dict(
        subject_id='user-1',
        tenant_id='company-1',
        signed_at=datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
        ip_address='203.0.113.10',
        user_agent='BaseTest/1.0',
        request_id='req-abc',
        channel='web',
    )
    base.update(overrides)
    return SignatoryContext(**base)


@pytest.mark.unit
class TestHashContent:

    def test_deterministic_for_same_text(self):
        assert hash_content('hola') == hash_content('hola')

    def test_bytes_and_str_utf8_match(self):
        assert hash_content('café') == hash_content('café'.encode('utf-8'))

    def test_different_content_different_hash(self):
        assert hash_content('a') != hash_content('b')

    def test_empty_raises(self):
        with pytest.raises(ValidationAppException) as exc:
            hash_content('')
        assert exc.value.code == AppErrorCode.SIGN_EMPTY_CONTENT


@pytest.mark.unit
class TestCanonicalPayload:

    def test_normalize_naive_datetime_as_utc(self):
        naive = datetime(2026, 1, 1, 10, 30, 0)
        assert normalize_utc(naive).endswith('Z')
        assert '2026-01-01T10:30:00' in normalize_utc(naive)

    def test_payload_is_stable_json(self):
        doc = _document()
        sig = _signatory()
        a = canonical_payload(doc, sig)
        b = canonical_payload(doc, sig)
        assert a == b
        assert a.startswith('{')
        assert '"content_hash"' in a


@pytest.mark.unit
class TestSealAndVerify:

    def test_roundtrip_valid(self):
        doc = _document()
        sig = _signatory()
        evidence = seal_signature(doc, sig, secret=SECRET)
        assert evidence.seal_algorithm == SEAL_ALGORITHM_V1
        assert len(evidence.seal) == 64

        check = verify_signature(
            doc, sig, evidence.seal,
            seal_algorithm=evidence.seal_algorithm,
            secret=SECRET,
        )
        assert check.valid is True
        assert check.reason is None

    def test_tampered_content_hash_fails(self):
        doc = _document('texto A')
        sig = _signatory()
        evidence = seal_signature(doc, sig, secret=SECRET)

        tampered = DocumentBinding(
            document_type=doc.document_type,
            document_version_id=doc.document_version_id,
            content_hash=hash_content('texto B'),
        )
        check = verify_signature(
            tampered, sig, evidence.seal, secret=SECRET,
        )
        assert check.valid is False
        assert check.reason == 'seal_mismatch'

    def test_tampered_subject_fails(self):
        doc = _document()
        sig = _signatory()
        evidence = seal_signature(doc, sig, secret=SECRET)

        other = _signatory(subject_id='user-2')
        check = verify_signature(doc, other, evidence.seal, secret=SECRET)
        assert check.valid is False
        assert check.reason == 'seal_mismatch'

    def test_wrong_secret_fails(self):
        doc = _document()
        sig = _signatory()
        evidence = seal_signature(doc, sig, secret=SECRET)
        check = verify_signature(doc, sig, evidence.seal, secret='other-secret')
        assert check.valid is False

    def test_empty_seal_fails(self):
        check = verify_signature(_document(), _signatory(), '', secret=SECRET)
        assert check.valid is False
        assert check.reason == 'empty_seal'

    def test_unsupported_algorithm_on_seal_raises(self):
        svc = DigitalSignatureService(secret=SECRET, algorithm='rsa-v9')
        with pytest.raises(ValidationAppException) as exc:
            svc.seal(_document(), _signatory())
        assert exc.value.code == AppErrorCode.SIGN_UNSUPPORTED_ALGORITHM

    def test_unsupported_algorithm_on_verify_returns_false(self):
        check = verify_signature(
            _document(), _signatory(), 'ab' * 32,
            seal_algorithm='unknown',
            secret=SECRET,
        )
        assert check.valid is False
        assert check.reason == 'unsupported_algorithm'


@pytest.mark.unit
class TestDocumentBindingValidation:

    def test_rejects_invalid_hash(self):
        with pytest.raises(ValidationError):
            DocumentBinding(
                document_type='tos',
                document_version_id='1',
                content_hash='not-a-hash',
            )

    def test_require_document_binding_raises_sign_invalid(self):
        from core.signing import require_document_binding

        with pytest.raises(ValidationAppException) as exc:
            require_document_binding(
                document_type='tos',
                document_version_id='1',
                content_hash='not-a-hash',
            )
        assert exc.value.code == AppErrorCode.SIGN_INVALID_BINDING



@pytest.mark.unit
class TestConfigAndRegistry:

    def test_sign_codes_registered(self):
        for code in (
            AppErrorCode.SIGN_SECRET_MISSING,
            AppErrorCode.SIGN_EMPTY_CONTENT,
            AppErrorCode.SIGN_UNSUPPORTED_ALGORITHM,
            AppErrorCode.SIGN_INVALID_BINDING,
        ):
            assert code in ERROR_REGISTRY

    @override_settings(SIGNING_SECRET_KEY='from-settings', SECRET_KEY='django-fallback')
    def test_service_reads_signing_secret_from_settings(self):
        svc = get_signature_service()
        a = svc.seal(_document(), _signatory())
        b = seal_signature(_document(), _signatory(), secret='from-settings')
        assert a.seal == b.seal

    @override_settings(
        SIGNING_SECRET_KEY='',
        SECRET_KEY='django-fallback-only',
        DEBUG=True,
    )
    def test_falls_back_to_django_secret_key_when_debug(self):
        a = get_signature_service().seal(_document(), _signatory())
        b = seal_signature(_document(), _signatory(), secret='django-fallback-only')
        assert a.seal == b.seal

    @override_settings(
        SIGNING_SECRET_KEY='',
        SECRET_KEY='django-fallback-only',
        DEBUG=False,
    )
    def test_requires_signing_secret_when_not_debug(self):
        from django.core.exceptions import ImproperlyConfigured

        with pytest.raises(ImproperlyConfigured, match='SIGNING_SECRET_KEY'):
            get_signature_service().seal(_document(), _signatory())

    def test_empty_explicit_secret_raises(self):
        with pytest.raises(ServerException) as exc:
            DigitalSignatureService(secret=b'')
        assert exc.value.code == AppErrorCode.SIGN_SECRET_MISSING
