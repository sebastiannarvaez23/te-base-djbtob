"""Pendientes de firma client para un usuario autenticado."""

from __future__ import annotations

from typing import List, Optional, Tuple

from platform.features.compliance.policy.policy.application.country_resolve import (
    resolve_company_policy_country,
)
from platform.features.compliance.policy.policy.application.sign_use_cases import (
    ListPendingPoliciesUseCase,
)
from platform.features.compliance.policy.policy.domain.enums import PolicySubjectType
from platform.features.compliance.policy.policy.application.required_policy_codes import (
    get_client_login_required_policy_codes,
)
from platform.features.compliance.policy.policy.domain.schemas import (
    PendingPolicySchema,
    SignatoryRef,
)
from platform.features.compliance.policy.policy.infrastructure.repositories import (
    DjangoPolicySignatureRepository,
)


def pending_policies_for_user(user) -> Tuple[List[PendingPolicySchema], Optional[str]]:
    """Lista published sin firma (códigos required-on-login) + país ISO."""
    country = resolve_company_policy_country(getattr(user, 'company', None))
    if not country or user is None:
        return [], country

    subject = SignatoryRef(
        subject_type=PolicySubjectType.CLIENT,
        subject_id=str(user.id),
        tenant_id=str(getattr(user, 'company_id', None) or getattr(user.company, 'id', '')),
    )
    items = ListPendingPoliciesUseCase(DjangoPolicySignatureRepository()).execute(
        subject=subject,
        country=country,
        policy_codes=get_client_login_required_policy_codes(),
    )
    return items, country
