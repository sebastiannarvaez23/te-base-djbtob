"""Unit tests for privacy country binding and registration country resolve."""

import pytest

from client.features.security.lifecycle.onboarding.application.privacy import (
    bind_privacy_country_to_company,
    resolve_registration_country_code,
)
from core.errors import AppErrorCode, OnboardingException


@pytest.mark.unit
def test_resolve_registration_country_from_country_code():
    assert resolve_registration_country_code({'country_code': 'co'}) == 'CO'


@pytest.mark.unit
def test_resolve_registration_country_from_iso_country_field():
    assert resolve_registration_country_code({'country': 'MX'}) == 'MX'


@pytest.mark.unit
def test_bind_privacy_country_accepts_matching_iso():
    assert bind_privacy_country_to_company(
        privacy_country='co',
        company_data={'country_code': 'CO'},
    ) == 'CO'


@pytest.mark.unit
def test_bind_privacy_country_rejects_mismatch():
    with pytest.raises(OnboardingException) as exc:
        bind_privacy_country_to_company(
            privacy_country='MX',
            company_data={'country_code': 'CO'},
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE


@pytest.mark.unit
def test_bind_privacy_country_rejects_missing_company_country():
    with pytest.raises(OnboardingException) as exc:
        bind_privacy_country_to_company(
            privacy_country='CO',
            company_data={'country': 'Colombia'},
        )
    assert exc.value.code == AppErrorCode.ONBOARDING_PRIVACY_STALE
