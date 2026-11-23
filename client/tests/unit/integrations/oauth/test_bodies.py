"""Unit tests — RequestBody validation for OAuth endpoints."""

import pytest

from client.features.integrations.oauth.client.presentation.bodies import (
    CreateIntegrationApplicationBody,
    IssueTokenBody,
    UpdateIntegrationApplicationBody,
)
from core.validators.codes import ValidationCode


def _codes(errors, field):
    return {e.code for e in errors if e.field == field}


@pytest.mark.unit
class TestCreateIntegrationApplicationBody:

    def test_valid_payload_applies_defaults(self):
        body = CreateIntegrationApplicationBody({'name': 'ERP Bridge', 'scopes': ['orders:read']})
        ok, errors = body.validate()
        assert ok is True and errors == []
        assert body.validated_data == {
            'name': 'ERP Bridge',
            'description': '',
            'environment': 'CLIENT_TEST',
            'scopes': ['orders:read'],
        }

    def test_name_and_scopes_required(self):
        ok, errors = CreateIntegrationApplicationBody({}).validate()
        assert ok is False
        assert ValidationCode.REQUIRED in _codes(errors, 'name')
        assert ValidationCode.REQUIRED in _codes(errors, 'scopes')
        assert all(isinstance(e.detail, str) and e.detail for e in errors)

    @pytest.mark.parametrize('name, code', [
        ('A', ValidationCode.MIN_LENGTH),
        ('x' * 121, ValidationCode.MAX_LENGTH),
        (42, ValidationCode.INVALID_TYPE),
    ])
    def test_name_rules(self, name, code):
        ok, errors = CreateIntegrationApplicationBody({'name': name, 'scopes': ['orders:read']}).validate()
        assert ok is False
        assert code in _codes(errors, 'name')

    def test_description_max_length(self):
        ok, errors = CreateIntegrationApplicationBody({
            'name': 'App', 'scopes': ['orders:read'], 'description': 'd' * 2001,
        }).validate()
        assert ValidationCode.MAX_LENGTH in _codes(errors, 'description')

    def test_invalid_environment_choice(self):
        ok, errors = CreateIntegrationApplicationBody({
            'name': 'App', 'scopes': ['orders:read'], 'environment': 'PROSANDBOX',
        }).validate()
        assert ok is False
        assert ValidationCode.INVALID_CHOICE in _codes(errors, 'environment')

    def test_scopes_must_be_list(self):
        ok, errors = CreateIntegrationApplicationBody({'name': 'App', 'scopes': 'orders:read'}).validate()
        assert ValidationCode.INVALID_TYPE in _codes(errors, 'scopes')

    def test_scopes_cannot_be_empty(self):
        ok, errors = CreateIntegrationApplicationBody({'name': 'App', 'scopes': []}).validate()
        assert ValidationCode.MIN_ITEMS in _codes(errors, 'scopes')

    def test_scopes_max_items(self):
        ok, errors = CreateIntegrationApplicationBody({
            'name': 'App', 'scopes': ['orders:read'] * 33,
        }).validate()
        assert ValidationCode.MAX_ITEMS in _codes(errors, 'scopes')

    def test_scope_item_wrong_type(self):
        ok, errors = CreateIntegrationApplicationBody({'name': 'App', 'scopes': [123]}).validate()
        assert ValidationCode.INVALID_TYPE in _codes(errors, 'scopes[0]')

    def test_scope_item_must_look_like_a_functionality_key(self):
        ok, errors = CreateIntegrationApplicationBody({
            'name': 'App', 'scopes': ['orders:read', 'Admin All!'],
        }).validate()
        assert not ok
        assert ValidationCode.INVALID_PATTERN in _codes(errors, 'scopes[1]')

    def test_scope_item_max_length(self):
        ok, errors = CreateIntegrationApplicationBody({
            'name': 'App', 'scopes': ['a' * 101],
        }).validate()
        assert ValidationCode.MAX_LENGTH in _codes(errors, 'scopes[0]')

    def test_rejects_unknown_fields(self):
        ok, errors = CreateIntegrationApplicationBody({
            'name': 'App', 'scopes': ['orders:read'], 'hack': True,
        }).validate()
        assert ok is False
        assert ValidationCode.UNKNOWN_FIELD in _codes(errors, 'hack')

    def test_error_response_is_english(self):
        body = CreateIntegrationApplicationBody({})
        _ok, errors = body.validate()
        response = body.error_response(errors)
        assert response.status_code == 400
        assert response.data['message'] == 'Request body validation error.'
        assert response.data['type'] == 'error'
        assert response.data['errors'][0]['detail'].startswith("Field '")


@pytest.mark.unit
class TestUpdateIntegrationApplicationBody:

    def test_partial_update_ok(self):
        body = UpdateIntegrationApplicationBody({'name': 'Renamed App'})
        ok, _errors = body.validate()
        assert ok is True
        assert body.validated_data == {'name': 'Renamed App'}

    def test_empty_body_is_valid(self):
        ok, _errors = UpdateIntegrationApplicationBody({}).validate()
        assert ok is True

    def test_status_is_not_editable(self):
        ok, errors = UpdateIntegrationApplicationBody({'status': 'ACTIVE'}).validate()
        assert ok is False
        assert ValidationCode.UNKNOWN_FIELD in _codes(errors, 'status')

    def test_client_id_is_not_editable(self):
        ok, errors = UpdateIntegrationApplicationBody({'client_id': 'wa_x'}).validate()
        assert ValidationCode.UNKNOWN_FIELD in _codes(errors, 'client_id')

    def test_scopes_cannot_be_emptied(self):
        ok, errors = UpdateIntegrationApplicationBody({'scopes': []}).validate()
        assert ValidationCode.MIN_ITEMS in _codes(errors, 'scopes')

    def test_null_name_rejected(self):
        ok, errors = UpdateIntegrationApplicationBody({'name': None}).validate()
        assert ValidationCode.NULL_NOT_ALLOWED in _codes(errors, 'name')


@pytest.mark.unit
class TestIssueTokenBody:

    def test_valid_token_request(self):
        ok, _errors = IssueTokenBody({
            'grant_type': 'client_credentials',
            'client_id': 'wa_abcdefghijk',
            'client_secret': 'x' * 32,
        }).validate()
        assert ok is True

    def test_client_secret_min_length(self):
        ok, errors = IssueTokenBody({
            'grant_type': 'client_credentials',
            'client_id': 'wa_abcdefghijk',
            'client_secret': 'short',
        }).validate()
        assert ValidationCode.MIN_LENGTH in _codes(errors, 'client_secret')

    def test_wrong_types(self):
        ok, errors = IssueTokenBody({
            'grant_type': 1,
            'client_id': True,
            'client_secret': ['x'],
        }).validate()
        assert ok is False
        assert {e.field for e in errors} >= {'grant_type', 'client_id', 'client_secret'}

    def test_unknown_field(self):
        ok, errors = IssueTokenBody({
            'grant_type': 'client_credentials',
            'client_id': 'wa_abcdefghijk',
            'client_secret': 'x' * 32,
            'audience': 'x',
        }).validate()
        assert ValidationCode.UNKNOWN_FIELD in _codes(errors, 'audience')
