"""Exige la firma vigente de COMPANY-DEREGISTRATION para el self-close."""

from __future__ import annotations

from uuid import UUID

from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ValidationAppException,
)

from platform.features.company.tenant.company.domain.lifecycle import (
    COMPANY_DEREGISTRATION_POLICY_CODE,
)
from platform.features.compliance.policy.policy.domain.enums import (
    PolicyAudience,
    PolicyCountryStatus,
    PolicySubjectType,
)
from platform.features.compliance.policy.policy.domain.interfaces import (
    IPolicyRepository,
    IPolicySignatureRepository,
)
from platform.features.compliance.policy.policy.domain.schemas import (
    SignatoryRef,
    normalize_country,
)
from core.trace import trace_layer


class RequireDeregistrationPolicySignatureUseCase:
    """Rechaza el cierre si el administrador no firmó la versión publicada."""

    def __init__(
        self,
        policies: IPolicyRepository,
        signatures: IPolicySignatureRepository,
    ):
        self.policies = policies
        self.signatures = signatures

    @trace_layer('application')
    def execute(
        self,
        *,
        actor_user_id: UUID,
        company_id: UUID,
        country: str | None,
    ) -> None:
        if not country:
            raise ValidationAppException(AppErrorCode.POLICY_INVALID_COUNTRY)
        try:
            iso = normalize_country(country)
        except ValueError as exc:
            raise ValidationAppException(AppErrorCode.POLICY_INVALID_COUNTRY) from exc

        policy = self.policies.get_by_code(COMPANY_DEREGISTRATION_POLICY_CODE)
        if (
            not policy
            or not policy.is_active
            or policy.audience != PolicyAudience.CLIENT
        ):
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)

        row = self.policies.get_country(policy.id, iso)
        if not row:
            raise NotFoundException(AppErrorCode.POLICY_COUNTRY_NOT_FOUND)
        if row.status != PolicyCountryStatus.PUBLISHED:
            raise ConflictException(AppErrorCode.POLICY_NOT_SIGNABLE)

        existing = self.signatures.find_for_version(
            subject=SignatoryRef(
                subject_type=PolicySubjectType.CLIENT,
                subject_id=str(actor_user_id),
                tenant_id=str(company_id),
            ),
            policy_country_id=row.id,
            content_hash=row.content_hash,
        )
        if not existing:
            raise ValidationAppException(AppErrorCode.COMPANY_CLOSE_POLICY_REQUIRED)
