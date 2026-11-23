"""Aceptación y firma de políticas client durante el finalize de onboarding."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from uuid import UUID

from core.errors import AppErrorCode, ConflictException, OnboardingException
from core.storage import MinioStorageService

from platform.features.compliance.policy.policy.application.required_policy_codes import (
    get_client_onboarding_required_policy_codes,
)
from platform.features.compliance.policy.policy.application.sign_use_cases import SignPolicyUseCase
from platform.features.compliance.policy.policy.domain.enums import PolicyAudience, PolicySubjectType
from platform.features.compliance.policy.policy.domain.interfaces import IPolicyRepository
from platform.features.compliance.policy.policy.domain.required_codes import (
    ONBOARDING_PRIVACY_POLICY_CODE,
    ONBOARDING_TERMS_POLICY_CODE,
)
from platform.features.compliance.policy.policy.domain.schemas import (
    PolicyCountryContentSchema,
    SignPolicyContextSchema,
    SignPolicySchema,
    SignatoryRef,
    normalize_code,
    normalize_country,
)
from platform.features.compliance.policy.policy.infrastructure.repositories import (
    DjangoPolicyRepository,
    DjangoPolicySignatureRepository,
)

logger = logging.getLogger('app.api')


def _required_code_for(policy_code: str):
    if policy_code == ONBOARDING_TERMS_POLICY_CODE:
        return AppErrorCode.ONBOARDING_TERMS_REQUIRED
    return AppErrorCode.ONBOARDING_PRIVACY_REQUIRED


def _stale_code_for(policy_code: str):
    if policy_code == ONBOARDING_TERMS_POLICY_CODE:
        return AppErrorCode.ONBOARDING_TERMS_STALE
    return AppErrorCode.ONBOARDING_PRIVACY_STALE


def resolve_registration_country_code(company_data: dict | None) -> Optional[str]:
    """ISO del país de la empresa: ``country_code`` o ``country`` si ya es ISO-2."""
    data = company_data or {}
    raw = (data.get('country_code') or '').strip().upper()
    if not raw:
        candidate = (data.get('country') or '').strip().upper()
        if len(candidate) == 2 and candidate.isalpha():
            raw = candidate
    if not raw:
        return None
    try:
        return normalize_country(raw)
    except ValueError:
        return None


def bind_privacy_country_to_company(
    *,
    privacy_country: str,
    company_data: dict | None,
) -> str:
    """Obliga el país de la política al ISO de la empresa registrada."""
    company_country = resolve_registration_country_code(company_data)
    if not company_country:
        raise OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_STALE)
    try:
        requested = normalize_country(privacy_country)
    except ValueError as exc:
        raise OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_STALE) from exc
    if requested != company_country:
        raise OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_STALE)
    return company_country


def assert_policy_acceptance(
    *,
    policy_code: str,
    accepted: bool,
    content_hash: str,
    country: str,
    repository: IPolicyRepository,
) -> PolicyCountryContentSchema:
    """Exige aceptación explícita y que el hash coincida con la versión publicada."""
    try:
        code = normalize_code(policy_code)
    except ValueError as exc:
        raise OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_STALE) from exc

    required = _required_code_for(code)
    stale = _stale_code_for(code)

    if not accepted:
        raise OnboardingException(required)

    try:
        country = normalize_country(country)
    except ValueError as exc:
        raise OnboardingException(stale) from exc

    expected_hash = (content_hash or '').strip().lower()
    if not expected_hash or len(expected_hash) != 64:
        raise OnboardingException(required)

    policy = repository.get_by_code(code)
    if (
        not policy
        or not policy.is_active
        or policy.audience != PolicyAudience.CLIENT
    ):
        raise OnboardingException(stale)

    row = repository.get_country(policy.id, country)
    if not row or row.content_hash.lower() != expected_hash:
        raise OnboardingException(stale)

    return PolicyCountryContentSchema(
        policy_id=policy.id,
        policy_code=policy.code,
        audience=policy.audience,
        country=row.country,
        version=row.version,
        status=row.status,
        title=row.title,
        markdown='',
        object_key=row.object_key,
        content_hash=row.content_hash,
        byte_size=row.byte_size,
        change_summary=getattr(row, 'change_summary', '') or '',
        updated_at=row.updated_at,
    )


def assert_privacy_acceptance(
    *,
    accepted: bool,
    content_hash: str,
    country: str,
    repository: IPolicyRepository,
) -> PolicyCountryContentSchema:
    """Compat: sella PRIVACY-POLICY (siempre requerida en onboarding)."""
    return assert_policy_acceptance(
        policy_code=ONBOARDING_PRIVACY_POLICY_CODE,
        accepted=accepted,
        content_hash=content_hash,
        country=country,
        repository=repository,
    )


def collect_onboarding_policies_to_seal(
    *,
    country: str,
    content_hashes: dict[str, str],
    accepted_by_code: Dict[str, bool],
    repository: IPolicyRepository,
) -> List[PolicyCountryContentSchema]:
    """Valida y recoge políticas a sellar en finalize (privacy + terms).

    Cada código exige su propio flag de aceptación y hash publicado.
    """
    country = normalize_country(country)
    codes = get_client_onboarding_required_policy_codes()
    to_seal: List[PolicyCountryContentSchema] = []
    hashes = {
        str(code).strip().upper(): (hash_value or '').strip()
        for code, hash_value in (content_hashes or {}).items()
        if code
    }
    accepted_map = {
        str(code).strip().upper(): bool(flag)
        for code, flag in (accepted_by_code or {}).items()
        if code
    }

    for code in codes:
        to_seal.append(
            assert_policy_acceptance(
                policy_code=code,
                accepted=accepted_map.get(code, False),
                content_hash=hashes.get(code, ''),
                country=country,
                repository=repository,
            ),
        )

    if not to_seal:
        raise OnboardingException(AppErrorCode.ONBOARDING_PRIVACY_REQUIRED)
    return to_seal


def build_onboarding_content_hashes(
    *,
    privacy_content_hash: str,
    terms_content_hash: str,
) -> dict[str, str]:
    """Mapa código → hash que el finalize espera en el body."""
    return {
        ONBOARDING_PRIVACY_POLICY_CODE: privacy_content_hash,
        ONBOARDING_TERMS_POLICY_CODE: terms_content_hash,
    }


def build_onboarding_acceptances(
    *,
    privacy_accepted: bool,
    terms_accepted: bool,
) -> dict[str, bool]:
    """Mapa código → flag de aceptación del body de finalize."""
    return {
        ONBOARDING_PRIVACY_POLICY_CODE: bool(privacy_accepted),
        ONBOARDING_TERMS_POLICY_CODE: bool(terms_accepted),
    }


def sign_onboarding_privacy(
    *,
    user_id: UUID,
    company_id: UUID,
    content: PolicyCountryContentSchema,
    context: SignPolicyContextSchema,
) -> None:
    """Sella la evidencia append-only de firma (mismo camino que el mundo client)."""
    sign_onboarding_policies(
        user_id=user_id,
        company_id=company_id,
        contents=[content],
        context=context,
    )


def sign_onboarding_policies(
    *,
    user_id: UUID,
    company_id: UUID,
    contents: List[PolicyCountryContentSchema],
    context: SignPolicyContextSchema,
) -> None:
    """Sella cada política recaudada en onboarding."""
    use_case = SignPolicyUseCase(
        DjangoPolicyRepository(),
        DjangoPolicySignatureRepository(),
        MinioStorageService(),
    )
    for content in contents:
        try:
            use_case.execute(
                SignPolicySchema(
                    policy_id=content.policy_id,
                    country=content.country,
                    signatory=SignatoryRef(
                        subject_type=PolicySubjectType.CLIENT,
                        subject_id=str(user_id),
                        tenant_id=str(company_id),
                    ),
                    context=context,
                ),
            )
        except ConflictException as exc:
            if getattr(exc, 'code', None) == AppErrorCode.POLICY_ALREADY_SIGNED:
                continue
            raise
