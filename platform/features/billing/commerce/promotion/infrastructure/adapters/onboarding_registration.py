"""Adapter to read/update the onboarding registration for promotion apply."""

import uuid

from platform.features.billing.commerce.promotion.domain.interfaces import IOnboardingRegistrationPort


class DjangoOnboardingRegistration(IOnboardingRegistrationPort):

    def _repo(self):
        from client.features.security.lifecycle.onboarding.infrastructure.repositories import (
            DjangoCompanyRegistrationRepository,
        )
        return DjangoCompanyRegistrationRepository()

    def get(self, registration_id: uuid.UUID):
        return self._repo().get(registration_id)

    def save_promotion_apply(self, registration_id, *, serial: str, promotion_preview: dict) -> None:
        self._repo().save_promotion_apply(
            registration_id, serial=serial, promotion_preview=promotion_preview,
        )
