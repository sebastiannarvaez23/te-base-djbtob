"""Unit tests — strict Pydantic parse helpers for OAuth schemas."""

import pytest

from client.features.integrations.oauth.client.domain.schemas import (
    UpdateIntegrationApplicationSchema,
    parse_create_integration_application_schema,
    parse_issue_token_input_schema,
    parse_update_integration_application_schema,
)
from core.errors import AppErrorCode
from core.errors.exceptions import ValidationAppException


@pytest.mark.unit
class TestParseCreateSchema:

    def test_parses_valid(self):
        schema = parse_create_integration_application_schema(
            name='  ERP  ',
            description='  orders  ',
            environment='CLIENT_PROD',
            scopes=[' orders:write ', 'orders:read'],
        )
        assert schema.name == 'ERP'
        assert schema.description == 'orders'
        assert schema.environment == 'CLIENT_PROD'
        assert schema.scopes == ['orders:write', 'orders:read']

    def test_rejects_short_name(self):
        with pytest.raises(ValidationAppException) as exc:
            parse_create_integration_application_schema(name='A', scopes=['orders:read'])
        assert exc.value.code == AppErrorCode.VALIDATION_ERROR
        assert 'name' in exc.value.detail.lower()

    def test_rejects_whitespace_name(self):
        with pytest.raises(ValidationAppException):
            parse_create_integration_application_schema(name='   a   ', scopes=['orders:read'])

    def test_rejects_invalid_environment(self):
        with pytest.raises(ValidationAppException) as exc:
            parse_create_integration_application_schema(
                name='App', environment='PROSANDBOX', scopes=['orders:read'],
            )
        assert exc.value.code == AppErrorCode.VALIDATION_ERROR

    def test_requires_scopes(self):
        with pytest.raises(ValidationAppException) as exc:
            parse_create_integration_application_schema(name='App')
        assert 'scopes' in exc.value.detail

    def test_rejects_empty_scopes(self):
        with pytest.raises(ValidationAppException):
            parse_create_integration_application_schema(name='App', scopes=[])

    def test_rejects_blank_scope(self):
        with pytest.raises(ValidationAppException):
            parse_create_integration_application_schema(name='App', scopes=['  '])

    def test_rejects_too_long_scope(self):
        with pytest.raises(ValidationAppException):
            parse_create_integration_application_schema(name='App', scopes=['s' * 101])

    @pytest.mark.parametrize('bad', ['API.Orders', 'orders read', '-orders', 'órdenes.read', 'orders;drop'])
    def test_rejects_non_functionality_key_scope(self, bad):
        with pytest.raises(ValidationAppException) as exc:
            parse_create_integration_application_schema(name='App', scopes=[bad])
        assert 'functionality keys' in exc.value.detail

    def test_rejects_extra_fields(self):
        with pytest.raises(ValidationAppException):
            parse_create_integration_application_schema(
                name='App', scopes=['orders:read'], status='REVOKED',
            )


@pytest.mark.unit
class TestParseUpdateSchema:

    def test_status_is_not_part_of_update(self):
        with pytest.raises(ValidationAppException) as exc:
            parse_update_integration_application_schema(status='ACTIVE')
        assert exc.value.code == AppErrorCode.VALIDATION_ERROR

    def test_partial(self):
        schema = parse_update_integration_application_schema(name='  New  ')
        assert schema.name == 'New'
        assert schema.has_changes() is True

    def test_empty_has_no_changes(self):
        assert UpdateIntegrationApplicationSchema().has_changes() is False

    def test_description_stripped(self):
        assert parse_update_integration_application_schema(description='  x  ').description == 'x'

    def test_scopes_normalized(self):
        schema = parse_update_integration_application_schema(scopes=[' orders:read '])
        assert schema.scopes == ['orders:read']

    def test_rejects_empty_scopes(self):
        with pytest.raises(ValidationAppException):
            parse_update_integration_application_schema(scopes=[])


@pytest.mark.unit
class TestParseIssueTokenSchema:

    def test_parses_client_credentials(self):
        schema = parse_issue_token_input_schema(
            grant_type=' client_credentials ',
            client_id='wa_abcdefghijk',
            client_secret='s' * 32,
            scope='  orders:read  ',
        )
        assert schema.grant_type == 'client_credentials'
        assert schema.scope == 'orders:read'
        assert 's' * 32 not in repr(schema)

    def test_blank_scope_becomes_none(self):
        schema = parse_issue_token_input_schema(
            grant_type='client_credentials',
            client_id='wa_abcdefghijk',
            client_secret='s' * 32,
            scope='   ',
        )
        assert schema.scope is None

    def test_rejects_unsupported_grant(self):
        with pytest.raises(ValidationAppException) as exc:
            parse_issue_token_input_schema(
                grant_type='password',
                client_id='wa_abcdefghijk',
                client_secret='s' * 32,
            )
        assert exc.value.code == AppErrorCode.VALIDATION_ERROR
        assert 'grant_type' in exc.value.detail.lower()

    def test_rejects_non_string_grant(self):
        with pytest.raises(ValidationAppException) as exc:
            parse_issue_token_input_schema(
                grant_type=1,
                client_id='wa_abcdefghijk',
                client_secret='s' * 32,
            )
        assert 'grant_type' in exc.value.detail

    def test_rejects_short_secret(self):
        with pytest.raises(ValidationAppException) as exc:
            parse_issue_token_input_schema(
                grant_type='client_credentials',
                client_id='wa_abcdefghijk',
                client_secret='short',
            )
        assert exc.value.code == AppErrorCode.VALIDATION_ERROR
