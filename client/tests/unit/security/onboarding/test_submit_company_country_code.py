"""Unit tests for company step country_code persistence and schema validation."""

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
    OnboardingStep,
)
from client.features.security.lifecycle.onboarding.domain.schemas import CompanyStepSchema

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


@pytest.mark.unit
def test_company_step_schema_normalizes_country_code():
    data = CompanyStepSchema(
        name='Acme',
        nit='900123456',
        address='Cra 1 # 2-3',
        country='Colombia',
        country_code='co',
        state='Cundinamarca',
        city='Bogota',
        city_id=CITY_ID,
    )
    assert data.country_code == 'CO'
    assert data.city_id == CITY_ID


@pytest.mark.unit
@pytest.mark.parametrize('bad_code', ['', 'C', 'COL', 'C1', '12'])
def test_company_step_schema_rejects_invalid_country_code(bad_code):
    with pytest.raises(ValidationError):
        CompanyStepSchema(
            name='Acme',
            nit='900123456',
            address='Cra 1 # 2-3',
            country='Colombia',
            country_code=bad_code,
            state='Cundinamarca',
            city='Bogota',
            city_id=CITY_ID,
        )


@pytest.mark.unit
def test_submit_company_persists_country_code():
    reg = _reg()
    repo = MagicMock()
    repo.get.return_value = reg
    company_repo = MagicMock()
    company_repo.get_by_nit.return_value = None
    company_repo.get_by_schema_name.return_value = None
    schema = CompanyStepSchema(
        name='Acme Logistics',
        nit='900123456-7',
        address='Cra 1 # 2-3',
        country='Colombia',
        country_code='co',
        state='Cundinamarca',
        city='Bogota',
        city_id=CITY_ID,
    )

    with patch(
        'client.features.security.lifecycle.onboarding.application.use_cases.submit_company'
        '.ensure_step_writable',
    ), patch(
        'client.features.security.lifecycle.onboarding.application.use_cases.submit_company'
        '.assert_active_geo_city',
    ):
        state = SubmitCompanyStepUseCase(repo, company_repo).execute(reg.id, schema)

    repo.save_company_step.assert_called_once()
    call = repo.save_company_step.call_args
    saved_schema = call.args[1]
    assert saved_schema.country_code == 'CO'
    assert state.company_data['country_code'] == 'CO'
    assert state.company_data['country'] == 'Colombia'
    assert state.company_data['city_id'] == str(CITY_ID)
    assert state.company_data_completed is True
