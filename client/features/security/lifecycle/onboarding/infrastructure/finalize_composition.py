"""Composition root for FinalizeOnboardingUseCase (Django adapters)."""

from __future__ import annotations

from client.features.security.lifecycle.onboarding.application.use_cases.finalize import (
    FinalizeOnboardingUseCase,
)
from client.features.security.lifecycle.onboarding.domain.interfaces import (
    ICompanyRegistrationRepository,
)
from client.features.security.lifecycle.onboarding.infrastructure.finalize_side_effects import (
    DjangoFinalizeSideEffects,
)
from client.features.security.lifecycle.onboarding.infrastructure.repositories import (
    DjangoCompanyRegistrationRepository,
)
from platform.features.company.tenant.company.infrastructure.repositories import (
    DjangoCompanyRepository,
)
from platform.features.compliance.policy.policy.infrastructure.repositories import (
    DjangoPolicyRepository,
)


def compose_finalize_use_case(
    repository: ICompanyRegistrationRepository | None = None,
) -> FinalizeOnboardingUseCase:
    repo = repository or DjangoCompanyRegistrationRepository()
    return FinalizeOnboardingUseCase(
        repo,
        DjangoCompanyRepository(),
        DjangoPolicyRepository(),
        DjangoFinalizeSideEffects(repo),
    )
