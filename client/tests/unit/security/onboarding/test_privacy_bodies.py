"""Unit tests for FinalizeOnboardingBody / privacy payload validation."""

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

import pytest

from client.features.security.lifecycle.onboarding.presentation.bodies import (
    CompanyStepBody,
    FinalizeOnboardingBody,
)


@pytest.mark.unit
def test_finalize_body_accepts_valid_privacy_payload():
    data, err = FinalizeOnboardingBody({
        'privacy_accepted': True,
        'privacy_content_hash': 'a' * 64,
        'privacy_country': 'co',
        'terms_accepted': True,
        'terms_content_hash': 'b' * 64,
    }).parse()
    assert err is None
    assert data['privacy_accepted'] is True
    assert data['privacy_content_hash'] == 'a' * 64
    assert data['terms_accepted'] is True
    assert data['terms_content_hash'] == 'b' * 64
    # pattern allows mixed case; coerce may keep as given depending on Field
    assert str(data['privacy_country']).upper() == 'CO' or data['privacy_country'] == 'co'


@pytest.mark.unit
def test_finalize_body_rejects_missing_fields():
    data, err = FinalizeOnboardingBody({}).parse()
    assert data is None
    assert err is not None


@pytest.mark.unit
def test_finalize_body_rejects_short_hash():
    data, err = FinalizeOnboardingBody({
        'privacy_accepted': True,
        'privacy_content_hash': 'abc',
        'privacy_country': 'CO',
        'terms_accepted': True,
        'terms_content_hash': 'b' * 64,
    }).parse()
    assert data is None
    assert err is not None


@pytest.mark.unit
def test_finalize_body_rejects_invalid_country():
    data, err = FinalizeOnboardingBody({
        'privacy_accepted': True,
        'privacy_content_hash': 'a' * 64,
        'privacy_country': 'COL',
        'terms_accepted': True,
        'terms_content_hash': 'b' * 64,
    }).parse()
    assert data is None
    assert err is not None


@pytest.mark.unit
def test_finalize_body_rejects_missing_terms():
    data, err = FinalizeOnboardingBody({
        'privacy_accepted': True,
        'privacy_content_hash': 'a' * 64,
        'privacy_country': 'CO',
    }).parse()
    assert data is None
    assert err is not None


@pytest.mark.unit
def test_company_body_requires_country_code():
    data, err = CompanyStepBody({
        'name': 'Acme',
        'nit': '900123456',
        'address': 'Cra 1 # 2-3',
        'country': 'Colombia',
        'state': 'Cundinamarca',
        'city': 'Bogota',
        'city_id': '0f15d58f-1ed6-4019-a3b7-22861f9dbc82',
    }).parse()
    assert data is None
    assert err is not None


@pytest.mark.unit
def test_company_body_requires_city_id():
    data, err = CompanyStepBody({
        'name': 'Acme',
        'nit': '900123456',
        'address': 'Cra 1 # 2-3',
        'country': 'Colombia',
        'country_code': 'CO',
        'state': 'Cundinamarca',
        'city': 'Bogota',
    }).parse()
    assert data is None
    assert err is not None


@pytest.mark.unit
def test_company_body_accepts_country_code():
    data, err = CompanyStepBody({
        'name': 'Acme',
        'nit': '900123456',
        'address': 'Cra 1 # 2-3',
        'country': 'Colombia',
        'country_code': 'CO',
        'state': 'Cundinamarca',
        'city': 'Bogota',
        'city_id': '0f15d58f-1ed6-4019-a3b7-22861f9dbc82',
    }).parse()
    assert err is None
    assert data['country_code'] == 'CO'
    assert str(data['city_id']) == '0f15d58f-1ed6-4019-a3b7-22861f9dbc82'
