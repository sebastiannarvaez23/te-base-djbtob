"""Admin-user step: identity document, second names, and phone country code."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

import pytest
from pydantic import ValidationError

from client.features.security.lifecycle.onboarding.application.use_cases.submit_admin_user import (
    SubmitAdminUserStepUseCase,
)
from client.features.security.lifecycle.onboarding.domain.enums import (
    OnboardingStatus,
    OnboardingStep,
)
from client.features.security.lifecycle.onboarding.domain.schemas import AdminUserStepSchema
from client.features.security.lifecycle.onboarding.presentation.bodies import AdminUserStepBody
from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType

RESOLVER_PATH = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '._common.StepResolver.resolve'
)
HASH_PATH = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '.submit_admin_user.make_password'
)
VALIDATE_PATH = (
    'client.features.security.lifecycle.onboarding.application.use_cases'
    '.submit_admin_user.validate_password'
)


def _orm_stub():
    reg = MagicMock()
    reg.id = uuid4()
    reg.status = OnboardingStatus.IN_PROGRESS.value
    reg.email = 'founder@example.com'
    reg.nit = '900123'
    reg.schema_name = 'acme'
    reg.company_data_completed = True
    reg.admin_user_completed = False
    reg.subscription_selected = False
    reg.payment_completed = False
    reg.requires_payment = False
    reg.subscription_id = None
    reg.company_data = {}
    reg.subscription_data = {}
    reg.admin_user_data = {}
    reg.payment_data = {}
    reg.expires_at = MagicMock(isoformat=lambda: '2026-05-05T00:00:00+00:00')
    reg.is_expired = lambda: False
    return reg


def _payload(**overrides):
    base = dict(
        email='owner@example.com',
        username='owner1',
        telephone='3001234567',
        phone_country_code='co',
        password='supersecret1',
        password_confirmation='supersecret1',
        first_name='Jane',
        second_name='Ann',
        last_name='Doe',
        second_last_name='Smith',
        document_type='CC',
        document_number='1144205897',
        birth_date='1990-05-15',
    )
    base.update(overrides)
    return base


@pytest.mark.unit
def test_admin_schema_normalizes_identity_fields():
    data = AdminUserStepSchema(**_payload())
    assert data.phone_country_code == 'CO'
    assert data.document_type is IdentityDocumentType.CEDULA_CIUDADANIA
    assert data.document_number == '1144205897'
    assert data.telephone == '3001234567'
    assert data.birth_date.isoformat() == '1990-05-15'
    public = data.to_public_dict()
    assert public['document_type'] == 'CC'
    assert 'password' not in public


@pytest.mark.unit
@pytest.mark.parametrize('doc_type', ['XX', '', 'cedula'])
def test_admin_schema_rejects_unknown_document_type(doc_type):
    with pytest.raises(ValidationError):
        AdminUserStepSchema(**_payload(document_type=doc_type))


@pytest.mark.unit
def test_admin_schema_allows_empty_second_name():
    data = AdminUserStepSchema(**_payload(second_name=''))
    assert data.second_name == ''


@pytest.mark.unit
@pytest.mark.parametrize('birth_date', ['2030-01-01', '2015-01-01', '1800-01-01', 'not-a-date', ''])
def test_admin_schema_rejects_invalid_birth_date(birth_date):
    with pytest.raises(ValidationError):
        AdminUserStepSchema(**_payload(birth_date=birth_date))


@pytest.mark.unit
def test_admin_body_rejects_underage_birth_date():
    data, err = AdminUserStepBody(_payload(birth_date='2015-06-01')).parse()
    assert data is None
    assert err is not None
    fields = [item['field'] for item in err.data['errors']]
    assert 'birth_date' in fields


@pytest.mark.unit
def test_admin_schema_rejects_short_second_name():
    with pytest.raises(ValidationError):
        AdminUserStepSchema(**_payload(second_name='A'))


@pytest.mark.unit
def test_admin_body_accepts_valid_identity_payload():
    data, err = AdminUserStepBody(_payload()).parse()
    assert err is None
    assert data['phone_country_code'] == 'CO'
    assert data['document_number'] == '1144205897'
    assert data['document_type'] == 'CC'


@pytest.mark.unit
def test_admin_body_rejects_invalid_document_type():
    data, err = AdminUserStepBody(_payload(document_type='XX')).parse()
    assert data is None
    assert err is not None


@pytest.mark.unit
def test_submit_admin_persists_identity_fields():
    reg = _orm_stub()
    repo = MagicMock()
    repo.get.return_value = reg
    repo.username_taken.return_value = False
    repo.email_taken.return_value = False
    schema = AdminUserStepSchema(**_payload())

    with patch(RESOLVER_PATH, return_value=OnboardingStep.SUBSCRIPTION), \
         patch(HASH_PATH, return_value='hashed-pwd'), \
         patch(VALIDATE_PATH):
        state = SubmitAdminUserStepUseCase(repo).execute(reg.id, schema)

    repo.save_admin_user_step.assert_called_once()
    saved = repo.save_admin_user_step.call_args.args[1]
    assert saved.second_last_name == 'Smith'
    assert saved.document_type is IdentityDocumentType.CEDULA_CIUDADANIA
    assert saved.phone_country_code == 'CO'
    assert state.admin_user_data['document_number'] == '1144205897'
    assert 'password_hash' not in state.admin_user_data


@pytest.mark.unit
def test_admin_schema_strips_document_grouping_dots():
    data = AdminUserStepSchema(**_payload(document_number='1.144.205.897'))
    assert data.document_number == '1144205897'


@pytest.mark.unit
def test_admin_schema_rejects_letters_on_cedula():
    with pytest.raises(ValidationError):
        AdminUserStepSchema(**_payload(document_number='AB1234'))


@pytest.mark.unit
def test_admin_schema_allows_alphanumeric_passport():
    data = AdminUserStepSchema(**_payload(document_type='PA', document_number='ab-123456'))
    assert data.document_number == 'AB-123456'


@pytest.mark.unit
def test_admin_schema_rejects_short_colombian_phone():
    with pytest.raises(ValidationError):
        AdminUserStepSchema(**_payload(telephone='300123456'))


@pytest.mark.unit
def test_admin_schema_accepts_foreign_phone_shorter_than_10():
    data = AdminUserStepSchema(**_payload(phone_country_code='US', telephone='5550123'))
    assert data.telephone == '5550123'


@pytest.mark.unit
def test_admin_body_strips_document_grouping_and_requires_co_phone():
    data, err = AdminUserStepBody(_payload(document_number='1.144.205.897')).parse()
    assert err is None
    assert data['document_number'] == '1144205897'

    bad, bad_err = AdminUserStepBody(_payload(telephone='300123456')).parse()
    assert bad is None
    assert bad_err is not None

