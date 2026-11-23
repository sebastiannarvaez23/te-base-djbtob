"""Autenticación dual del handbook con la cookie de cliente."""

from __future__ import annotations

from unittest.mock import patch

import jwt as pyjwt

import pytest
from django.test import RequestFactory, override_settings
from rest_framework.exceptions import AuthenticationFailed

from core.auth.cookies import ACCESS_CLIENT_COOKIE
from core.auth.jwt_service import create_access_token
from core.errors import AppErrorCode, AuthException
from handbook.core.authentication import HandbookAccessAuthentication

pytestmark = pytest.mark.unit

MODULE = 'handbook.core.authentication'


def _request(schema_name: str, context: str | None = 'client'):
    with patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=15):
        token = create_access_token(
            user_id='u1', user_type='client', schema_name=schema_name, session_id='sid-1',
        )
    headers = {'HTTP_X_AUTH_CONTEXT': context} if context else {}
    request = RequestFactory().get('/api/v1/docs/tree/', **headers)
    request.COOKIES[ACCESS_CLIENT_COOKIE] = token
    return request


@override_settings(SECRET_KEY='test-secret-key')
def test_stale_cookie_without_context_reads_as_anonymous():
    with patch(f'{MODULE}.session_exists', return_value=False):
        assert HandbookAccessAuthentication().authenticate(_request('public', context=None)) is None


@override_settings(SECRET_KEY='test-secret-key')
def test_closed_company_without_context_reads_as_anonymous():
    closed = AuthException(AppErrorCode.AUTH_COMPANY_CLOSED)
    with patch(f'{MODULE}.session_exists', return_value=True), \
            patch(f'{MODULE}.JWTAccessAuthentication.authenticate', side_effect=closed):
        assert HandbookAccessAuthentication().authenticate(_request('public', context=None)) is None


@override_settings(SECRET_KEY='test-secret-key')
def test_stale_cookie_with_declared_context_still_fails():
    with patch(f'{MODULE}.session_exists', return_value=False):
        with pytest.raises(AuthenticationFailed):
            HandbookAccessAuthentication().authenticate(_request('public'))


@override_settings(SECRET_KEY='test-secret-key')
def test_public_schema_token_uses_the_standard_client_authentication():
    expected = (object(), {'user_type': 'client'})
    with patch(f'{MODULE}.session_exists', return_value=True), \
            patch(f'{MODULE}.JWTAccessAuthentication.authenticate', return_value=expected) as standard:
        result = HandbookAccessAuthentication().authenticate(_request('public'))

    assert result is expected
    standard.assert_called_once()


@override_settings(SECRET_KEY='test-secret-key')
def test_tenant_schema_token_loads_the_user_inside_that_schema():
    with patch(f'{MODULE}.session_exists', return_value=True), \
            patch(f'{MODULE}.JWTAccessAuthentication.authenticate') as standard, \
            patch('django_tenants.utils.schema_context') as schema_context, \
            patch('django.contrib.auth.get_user_model') as get_user_model:
        user = object()
        get_user_model.return_value.objects.select_related.return_value.get.return_value = user
        result = HandbookAccessAuthentication().authenticate(_request('otra-empresa'))

    assert result[0] is user
    schema_context.assert_called_once_with('otra-empresa')
    standard.assert_not_called()


def _token_request(token, context=None):
    headers = {'HTTP_X_AUTH_CONTEXT': context} if context else {}
    request = RequestFactory().get('/api/v1/docs/tree/', **headers)
    if token:
        request.COOKIES[ACCESS_CLIENT_COOKIE] = token
    return request


def test_admin_context_uses_admin_authentication():
    expected = (object(), {'user_type': 'admin'})
    with patch(f'{MODULE}.JWTAdminAccessAuthentication.authenticate', return_value=expected):
        assert HandbookAccessAuthentication().authenticate(_token_request(None, 'admin')) is expected


def test_without_context_admin_session_wins_and_no_cookie_is_anonymous():
    expected = (object(), {'user_type': 'admin'})
    with patch(f'{MODULE}.JWTAdminAccessAuthentication.authenticate', return_value=expected):
        assert HandbookAccessAuthentication().authenticate(_token_request(None)) is expected
    with patch(f'{MODULE}.JWTAdminAccessAuthentication.authenticate', return_value=None):
        assert HandbookAccessAuthentication().authenticate(_token_request(None)) is None


@pytest.mark.parametrize('error, detail', [
    (pyjwt.ExpiredSignatureError(), 'Session expired.'),
    (pyjwt.InvalidTokenError(), 'Invalid session.'),
])
def test_bad_client_token_fails_with_declared_context(error, detail):
    with patch(f'{MODULE}.decode_access_token', side_effect=error):
        with pytest.raises(AuthenticationFailed) as exc:
            HandbookAccessAuthentication().authenticate(_token_request('tok', 'client'))
    assert str(exc.value.detail) == detail


def test_non_client_token_is_ignored():
    with patch(f'{MODULE}.decode_access_token', return_value={'user_type': 'admin'}):
        assert HandbookAccessAuthentication().authenticate(_token_request('tok', 'client')) is None


@override_settings(SECRET_KEY='test-secret-key')
def test_tenant_user_missing_fails():
    class Missing(Exception):
        pass

    with patch(f'{MODULE}.session_exists', return_value=True), \
            patch('django_tenants.utils.schema_context'), \
            patch('django.contrib.auth.get_user_model') as get_user_model:
        get_user_model.return_value.DoesNotExist = Missing
        get_user_model.return_value.objects.select_related.return_value.get.side_effect = Missing
        with pytest.raises(AuthenticationFailed):
            HandbookAccessAuthentication().authenticate(_request('otra-empresa'))
