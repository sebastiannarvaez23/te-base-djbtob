"""Casos de uso de firma digital de políticas (core.signing + evidencia append-only)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Sequence

from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    PermissionException,
    ServerException,
    ValidationAppException,
)
from core.signing import (
    SignatoryContext,
    seal_signature,
    verify_signature,
)
from core.signing import hash_content as hash_bytes
from core.ids import uuid7
from core.signing.service import require_document_binding
from core.storage import IStorageService

from ..domain.enums import PolicyAudience, PolicyCountryStatus, PolicySubjectType
from ..domain.interfaces import IPolicyRepository, IPolicySignatureRepository
from ..domain.paths import POLICY_BUCKET
from ..domain.schemas import (
    PendingPolicySchema,
    PolicySignatureSchema,
    PolicySignatureVerificationSchema,
    SignPolicySchema,
    SignatoryRef,
    normalize_country,
)
from core.trace import trace_layer

logger = logging.getLogger('app.api')


def _audience_matches(audience: PolicyAudience, subject_type: PolicySubjectType) -> bool:
    return audience.value == subject_type.value


class SignPolicyUseCase:
    """
    Firma la versión publicada de un país:
    1) valida audiencia / activo / no duplicado
    2) relee MinIO y comprueba content_hash
    3) sella con core.signing y persiste evidencia append-only
    """

    def __init__(
        self,
        policies: IPolicyRepository,
        signatures: IPolicySignatureRepository,
        storage: IStorageService,
    ):
        self.policies = policies
        self.signatures = signatures
        self.storage = storage

    @trace_layer('application')
    def execute(self, data: SignPolicySchema) -> PolicySignatureSchema:
        policy = self.policies.get_by_id(data.policy_id)
        if not policy:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        if not policy.is_active:
            raise ConflictException(AppErrorCode.POLICY_INACTIVE)
        if not _audience_matches(policy.audience, data.signatory.subject_type):
            raise PermissionException(AppErrorCode.POLICY_AUDIENCE_MISMATCH)

        row = self.policies.get_country(data.policy_id, data.country)
        if not row:
            raise NotFoundException(AppErrorCode.POLICY_COUNTRY_NOT_FOUND)
        if row.status != PolicyCountryStatus.PUBLISHED:
            raise ConflictException(AppErrorCode.POLICY_NOT_SIGNABLE)

        existing = self.signatures.find_for_version(
            subject=data.signatory,
            policy_country_id=row.id,
            content_hash=row.content_hash,
        )
        if existing:
            raise ConflictException(AppErrorCode.POLICY_ALREADY_SIGNED)

        try:
            raw = self.storage.download_file(POLICY_BUCKET, row.object_key)
        except Exception as exc:
            logger.exception('Sign: failed download %s', row.object_key)
            raise ServerException(
                AppErrorCode.POLICY_STORAGE_ERROR,
                context={'object_key': row.object_key, 'error': str(exc)},
            ) from exc

        live_hash = hash_bytes(raw)
        if live_hash != row.content_hash:
            raise ConflictException(AppErrorCode.POLICY_CONTENT_TAMPERED)

        signed_at = data.context.signed_at or datetime.now(timezone.utc)
        if signed_at.tzinfo is None:
            signed_at = signed_at.replace(tzinfo=timezone.utc)

        evidence = seal_signature(
            require_document_binding(
                document_type=policy.code,
                document_version_id=str(row.id),
                content_hash=row.content_hash,
            ),
            SignatoryContext(
                subject_id=data.signatory.subject_id,
                tenant_id=data.signatory.tenant_id,
                signed_at=signed_at,
                ip_address=data.context.ip_address,
                user_agent=data.context.user_agent,
                request_id=data.context.request_id,
                channel=data.context.channel or 'web',
            ),
        )

        record = PolicySignatureSchema(
            id=uuid7(),
            policy_id=policy.id,
            policy_code=policy.code,
            policy_country_id=row.id,
            country=row.country,
            content_hash=row.content_hash,
            subject_type=data.signatory.subject_type,
            subject_id=data.signatory.subject_id,
            tenant_id=data.signatory.tenant_id,
            signed_at=signed_at,
            seal=evidence.seal,
            seal_algorithm=evidence.seal_algorithm,
            canonical_payload=evidence.canonical_payload,
            ip_address=data.context.ip_address,
            user_agent=data.context.user_agent,
            request_id=data.context.request_id,
            channel=data.context.channel or 'web',
        )
        return self.signatures.create(record)


class ListPendingPoliciesUseCase:
    def __init__(self, signatures: IPolicySignatureRepository):
        self.signatures = signatures

    @trace_layer('application')
    def execute(
        self,
        *,
        subject: SignatoryRef,
        country: str,
        policy_codes: Sequence[str] | None = None,
    ) -> List[PendingPolicySchema]:
        try:
            country = normalize_country(country)
        except ValueError as exc:
            raise ValidationAppException(
                AppErrorCode.POLICY_INVALID_COUNTRY,
                override_detail=str(exc),
            ) from exc
        return self.signatures.list_pending_for_subject(
            subject=subject,
            country=country,
            policy_codes=policy_codes,
        )


class ListPolicySignaturesUseCase:
    def __init__(self, policies: IPolicyRepository, signatures: IPolicySignatureRepository):
        self.policies = policies
        self.signatures = signatures

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID, filters: dict | None = None) -> List[PolicySignatureSchema]:
        if not self.policies.get_by_id(policy_id):
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        return self.signatures.list_for_policy(policy_id, filters=filters)


class VerifyPolicySignatureUseCase:
    def __init__(self, signatures: IPolicySignatureRepository):
        self.signatures = signatures

    @trace_layer('application')
    def execute(self, signature_id: uuid.UUID) -> PolicySignatureVerificationSchema:
        row = self.signatures.get_by_id(signature_id)
        if not row:
            raise NotFoundException(AppErrorCode.POLICY_SIGNATURE_NOT_FOUND)

        check = verify_signature(
            require_document_binding(
                document_type=row.policy_code,
                document_version_id=str(row.policy_country_id),
                content_hash=row.content_hash,
            ),
            SignatoryContext(
                subject_id=row.subject_id,
                tenant_id=row.tenant_id,
                signed_at=row.signed_at,
                ip_address=row.ip_address,
                user_agent=row.user_agent,
                request_id=row.request_id,
                channel=row.channel,
            ),
            row.seal,
            seal_algorithm=row.seal_algorithm,
        )
        if not check.valid:
            return PolicySignatureVerificationSchema(
                signature_id=row.id,
                valid=False,
                reason=check.reason or 'seal_mismatch',
            )
        return PolicySignatureVerificationSchema(signature_id=row.id, valid=True, reason=None)
