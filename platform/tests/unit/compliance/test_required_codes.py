"""Unit tests for client login required policy codes."""

import pytest
from django.test import override_settings

from platform.features.compliance.policy.policy.application.required_policy_codes import (
    get_client_login_required_policy_codes,
    get_client_onboarding_required_policy_codes,
)
from platform.features.compliance.policy.policy.domain.required_codes import (
    DEFAULT_CLIENT_LOGIN_REQUIRED_POLICY_CODES,
    ONBOARDING_PRIVACY_POLICY_CODE,
    ONBOARDING_TERMS_POLICY_CODE,
    normalize_policy_codes,
)


@pytest.mark.unit
def test_normalize_policy_codes_uppercases_and_dedupes():
    assert normalize_policy_codes(['privacy-policy', ' DATA-PROCESSING ', 'PRIVACY-POLICY', '']) == (
        'PRIVACY-POLICY',
        'DATA-PROCESSING',
    )


@pytest.mark.unit
def test_normalize_empty():
    assert normalize_policy_codes(None) == ()
    assert normalize_policy_codes([]) == ()


@pytest.mark.unit
@override_settings(CLIENT_LOGIN_REQUIRED_POLICY_CODES=['PRIVACY-POLICY', 'DATA-PROCESSING'])
def test_get_codes_from_settings():
    assert get_client_login_required_policy_codes() == (
        'PRIVACY-POLICY',
        'DATA-PROCESSING',
    )


@pytest.mark.unit
@override_settings(CLIENT_LOGIN_REQUIRED_POLICY_CODES=[])
def test_get_codes_empty_settings_disables_gate():
    assert get_client_login_required_policy_codes() == ()


@pytest.mark.unit
@override_settings(CLIENT_LOGIN_REQUIRED_POLICY_CODES=['DATA-PROCESSING'])
def test_onboarding_always_seals_privacy_and_terms_only():
    codes = get_client_onboarding_required_policy_codes()
    assert codes == (
        ONBOARDING_PRIVACY_POLICY_CODE,
        ONBOARDING_TERMS_POLICY_CODE,
    )
    assert get_client_login_required_policy_codes() == ('DATA-PROCESSING',)


@pytest.mark.unit
def test_default_includes_privacy_and_terms():
    assert 'PRIVACY-POLICY' in DEFAULT_CLIENT_LOGIN_REQUIRED_POLICY_CODES
    assert 'TERMS-AND-CONDITIONS' in DEFAULT_CLIENT_LOGIN_REQUIRED_POLICY_CODES
    assert ONBOARDING_TERMS_POLICY_CODE == 'TERMS-AND-CONDITIONS'