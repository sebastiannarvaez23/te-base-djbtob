"""Company step: registered companies require a unique NIT; unregistered ones do not."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

import pytest
from pydantic import ValidationError

from client.features.security.lifecycle.onboarding.application.use_cases.submit_company import (
    SubmitCompanyStepUseCase,
)
from client.features.security.lifecycle.onboarding.domain.enums import (
    OnboardingStatus,
)
from client.features.security.lifecycle.onboarding.domain.schemas import CompanyStepSchema
from client.features.security.lifecycle.onboarding.presentation.bodies import CompanyStepBody
from core.errors import AppErrorCode, OnboardingException

CITY_ID = uuid4()


def _reg(**overrides):
    base = dict(
        id=uuid4(),
        status=OnboardingStatus.IN_PROGRESS.value,
        email='founder@example.com',
        nit='',
        schema_name='',
        company_data_completed=False,
        admin_user_completed=False,
        subscription_selected=False,
        payment_completed=False,
        requires_payment=False,
        subscription_id=None,
        company_data={},
        subscription_data={},
        admin_user_data={},
        payment_data={},
        expires_at=MagicMock(isoformat=lambda: '2026-05-05T00:00:00+00:00'),
    )
    base.update(overrides)
    reg = MagicMock()
    for k, v in base.items():
        setattr(reg, k, v)
    reg.is_expired = lambda: False
    return reg


def _schema(**overrides):
    base = dict(
        name='Acme Logistics',
        nit='900123456',
        is_registered=True,
        address='Cra 1 # 2-3',
        country='Colombia',
        country_code='CO',
        state='Cundinamarca',
        city='Bogota',
        city_id=CITY_ID,
    )
    base.update(overrides)
    return CompanyStepSchema(**base)


@pytest.mark.unit
def test_unregistered_company_clears_nit_on_schema():
    data = _schema(is_registered=False, nit='900123456')
    assert data.is_registered is False
    assert data.nit == ''


@pytest.mark.unit
def test_registered_company_requires_nit():
    with pytest.raises(ValidationError):
        _schema(is_registered=True, nit='')


@pytest.mark.unit
def test_company_body_unregistered_omits_nit():
    data, err = CompanyStepBody({
        'name': 'Acme',
        'is_registered': False,
        'address': 'Cra 1 # 2-3',
        'country': 'Colombia',
        'country_code': 'CO',
        'state': 'Cundinamarca',
        'city': 'Bogota',
        'city_id': str(CITY_ID),
    }).parse()
    assert err is None
    assert data['is_registered'] is False
    assert data['nit'] == ''


@pytest.mark.unit
def test_company_body_registered_without_nit_is_400():
    data, err = CompanyStepBody({
        'name': 'Acme',
        'is_registered': True,
        'address': 'Cra 1 # 2-3',
        'country': 'Colombia',
        'country_code': 'CO',
        'state': 'Cundinamarca',
        'city': 'Bogota',
        'city_id': str(CITY_ID),
    }).parse()
    assert data is None
    assert err is not None


@pytest.mark.unit
def test_submit_unregistered_company_skips_nit_uniqueness():
    reg = _reg()
    repo = MagicMock()
    repo.get.return_value = reg
    company_repo = MagicMock()
    company_repo.get_by_nit.return_value = None
    company_repo.get_by_schema_name.return_value = None
    schema = _schema(is_registered=False, nit='')

    with patch(
        'client.features.security.lifecycle.onboarding.application.use_cases.submit_company'
        '.ensure_step_writable',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.use_cases.submit_company'
        '.assert_active_geo_city',
    ):
        state = SubmitCompanyStepUseCase(repo, company_repo).execute(reg.id, schema)

    company_repo.get_by_nit.assert_not_called()
    assert state.company_data['is_registered'] is False
    assert state.company_data['nit'] == ''
    assert state.nit == ''


@pytest.mark.unit
def test_submit_registered_duplicate_nit_raises():
    reg = _reg()
    repo = MagicMock()
    repo.get.return_value = reg
    company_repo = MagicMock()
    company_repo.get_by_nit.return_value = MagicMock(id=uuid4())
    company_repo.get_by_schema_name.return_value = None

    with patch(
        'client.features.security.lifecycle.onboarding.application.use_cases.submit_company'
        '.ensure_step_writable',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.use_cases.submit_company'
        '.assert_active_geo_city',
    ):
        with pytest.raises(OnboardingException) as exc:
            SubmitCompanyStepUseCase(repo, company_repo).execute(reg.id, _schema())

    assert exc.value.code == AppErrorCode.ONBOARDING_DUPLICATE_NIT
    repo.save_company_step.assert_not_called()
