"""Company user create/update accepts the same identity fields as registration."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from client.features.security.identity.users.domain.schemas import (
    CreateCompanyUserSchema,
    UpdateCompanyUserSchema,
)
from client.features.security.identity.users.presentation.bodies import (
    CreateCompanyUserBody,
    UpdateCompanyUserBody,
)
from client.features.security.lifecycle.registration.domain.enums import IdentityDocumentType


def _payload(**overrides):
    base = dict(
        first_name='Jane',
        second_name='Ann',
        last_name='Doe',
        second_last_name='Smith',
        document_type='CC',
        document_number='1.144.205.897',
        birth_date='1990-05-15',
        email='jane@example.com',
        username='jane.doe',
        telephone='3001234567',
        rol_id=str(uuid4()),
    )
    base.update(overrides)
    return base


@pytest.mark.unit
def test_create_body_normalizes_identity_fields():
    data, err = CreateCompanyUserBody(_payload()).parse()
    assert err is None
    assert data['second_name'] == 'Ann'
    assert data['second_last_name'] == 'Smith'
    assert data['document_type'] == 'CC'
    assert data['document_number'] == '1144205897'
    assert data['birth_date'] == '1990-05-15'


@pytest.mark.unit
def test_create_body_allows_empty_second_name():
    data, err = CreateCompanyUserBody(_payload(second_name='')).parse()
    assert err is None
    assert data['second_name'] == ''


@pytest.mark.unit
def test_create_body_rejects_underage_birth_date():
    data, err = CreateCompanyUserBody(_payload(birth_date='2015-06-01')).parse()
    assert data is None
    assert err is not None
    fields = [item['field'] for item in err.data['errors']]
    assert 'birth_date' in fields


@pytest.mark.unit
def test_create_body_rejects_missing_identification():
    payload = _payload()
    payload.pop('document_type')
    payload.pop('document_number')
    data, err = CreateCompanyUserBody(payload).parse()
    assert data is None
    fields = [item['field'] for item in err.data['errors']]
    assert 'document_type' in fields
    assert 'document_number' in fields


@pytest.mark.unit
def test_create_schema_stores_identity():
    data = CreateCompanyUserSchema(**_payload(), company_id=uuid4())
    assert data.document_type is IdentityDocumentType.CEDULA_CIUDADANIA
    assert data.document_number == '1144205897'
    assert data.birth_date.isoformat() == '1990-05-15'
    assert data.second_last_name == 'Smith'


@pytest.mark.unit
@pytest.mark.parametrize('birth_date', ['2030-01-01', '2015-01-01', '1800-01-01', 'not-a-date'])
def test_create_schema_rejects_invalid_birth_date(birth_date):
    with pytest.raises(ValidationError):
        CreateCompanyUserSchema(**_payload(birth_date=birth_date), company_id=uuid4())


@pytest.mark.unit
def test_create_schema_rejects_letters_on_citizenship_id():
    with pytest.raises(ValidationError):
        CreateCompanyUserSchema(
            **_payload(document_number='AB123456'),
            company_id=uuid4(),
        )


@pytest.mark.unit
def test_update_body_accepts_identity_patch():
    data, err = UpdateCompanyUserBody({
        'second_name': 'Ann',
        'second_last_name': 'Smith',
        'document_type': 'PA',
        'document_number': 'AB-123456',
        'birth_date': '1990-05-15',
    }).parse()
    assert err is None
    assert data['document_type'] == 'PA'
    assert data['document_number'] == 'AB-123456'
    assert data['birth_date'] == '1990-05-15'


@pytest.mark.unit
def test_update_schema_keeps_identity_optional():
    data = UpdateCompanyUserSchema(first_name='Jane')
    assert data.second_name is None
    assert data.birth_date is None
    assert data.document_type is None
