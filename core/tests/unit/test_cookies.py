"""Unit tests for HttpOnly cookie helpers and JWT-based cookie authentication.

Tests cover:
  - Cookie names (access_admin, access_client, refresh_admin, refresh_client)
  - set_auth_cookies sets HttpOnly, SameSite, Domain, Path correctly
  - clear_auth_cookies deletes with correct domain/path
  - JWTAccessAuthentication reads access_client cookie
  - JWTAdminAccessAuthentication reads access_admin cookie
  - Missing / empty / expired / invalid cookies return None or raise AuthenticationFailed
  - X-Auth-Context header controls which authentication class runs
  - Session id (sid) in JWT enables immediate session kill
  - Token without sid (legacy) is rejected
"""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import override_settings

from core.auth.cookies import (
    ACCESS_ADMIN_COOKIE,
    ACCESS_CLIENT_COOKIE,
    DEVICE_CLIENT_COOKIE,
    DEVICE_COOKIE_MAX_AGE,
    REFRESH_ADMIN_COOKIE,
    REFRESH_CLIENT_COOKIE,
    clear_auth_cookies,
    clear_device_cookie,
    read_device_serial,
    set_auth_cookies,
    set_device_cookie,
)


def _make_request(cookies=None, auth_context=None):
    """Build a minimal mock request for authentication tests."""
    request = MagicMock()
    request.COOKIES = cookies or {}
    meta = {}
    if auth_context:
        meta['HTTP_X_AUTH_CONTEXT'] = auth_context
    request.META = meta
    return request


# ── Cookie name constants ────────────────────────────────────────────────────

class TestCookieNames(TestCase):

    def test_access_client_name(self):
        self.assertEqual(ACCESS_CLIENT_COOKIE, 'access_client')

    def test_access_admin_name(self):
        self.assertEqual(ACCESS_ADMIN_COOKIE, 'access_admin')

    def test_refresh_client_name(self):
        self.assertEqual(REFRESH_CLIENT_COOKIE, 'refresh_client')

    def test_refresh_admin_name(self):
        self.assertEqual(REFRESH_ADMIN_COOKIE, 'refresh_admin')

    def test_device_client_name(self):
        self.assertEqual(DEVICE_CLIENT_COOKIE, 'device_client')


# ── set_auth_cookies ─────────────────────────────────────────────────────────

class TestSetAuthCookies(TestCase):

    @override_settings(
        DEBUG=True,
        AUTH_COOKIE_DOMAIN='.base.local',
        AUTH_COOKIE_SAMESITE='Lax',
    )
    @patch('core.auth.cookies._access_max_age', return_value=1800)
    @patch('core.auth.cookies._refresh_max_age', return_value=1209600)
    def test_set_client_cookies(self, _mock_ref, _mock_acc):
        response = HttpResponse()
        set_auth_cookies(response, 'access-jwt', 'refresh-opaque')

        access = response.cookies.get('access_client')
        self.assertIsNotNone(access)
        self.assertEqual(access.value, 'access-jwt')
        self.assertTrue(access['httponly'])
        self.assertEqual(access['domain'], '.base.local')
        self.assertEqual(access['samesite'], 'Lax')
        self.assertEqual(access['path'], '/')
        self.assertEqual(access['max-age'], 1800)

        refresh = response.cookies.get('refresh_client')
        self.assertIsNotNone(refresh)
        self.assertEqual(refresh.value, 'refresh-opaque')
        self.assertEqual(refresh['max-age'], 1209600)

    @override_settings(
        DEBUG=True,
        AUTH_COOKIE_DOMAIN='.base.local',
        AUTH_COOKIE_SAMESITE='Lax',
    )
    @patch('core.auth.cookies._access_max_age', return_value=1800)
    @patch('core.auth.cookies._refresh_max_age', return_value=1209600)
    def test_set_admin_cookies(self, _mock_ref, _mock_acc):
        response = HttpResponse()
        set_auth_cookies(response, 'admin-access', 'admin-refresh', admin=True)

        self.assertEqual(response.cookies['access_admin'].value, 'admin-access')
        self.assertEqual(response.cookies['refresh_admin'].value, 'admin-refresh')

    @override_settings(
        DEBUG=True,
        AUTH_COOKIE_DOMAIN='.base.local',
        AUTH_COOKIE_SAMESITE='Lax',
    )
    @patch('core.auth.cookies._access_max_age', return_value=1800)
    @patch('core.auth.cookies._refresh_max_age', return_value=1209600)
    def test_client_and_admin_cookies_independent(self, _mock_ref, _mock_acc):
        response = HttpResponse()
        set_auth_cookies(response, 'c-access', 'c-refresh')
        set_auth_cookies(response, 'a-access', 'a-refresh', admin=True)

        self.assertEqual(response.cookies['access_client'].value, 'c-access')
        self.assertEqual(response.cookies['access_admin'].value, 'a-access')
        self.assertEqual(response.cookies['refresh_client'].value, 'c-refresh')
        self.assertEqual(response.cookies['refresh_admin'].value, 'a-refresh')

    @override_settings(DEBUG=False, AUTH_COOKIE_SAMESITE='Lax')
    @patch('core.auth.cookies._access_max_age', return_value=1800)
    @patch('core.auth.cookies._refresh_max_age', return_value=1209600)
    def test_production_mode_sets_secure(self, _mock_ref, _mock_acc):
        response = HttpResponse()
        set_auth_cookies(response, 'jwt', 'ref')

        self.assertTrue(response.cookies['access_client']['secure'])
        self.assertTrue(response.cookies['refresh_client']['secure'])

    @override_settings(
        DEBUG=True,
        AUTH_COOKIE_DOMAIN='.base.local',
        AUTH_COOKIE_SAMESITE='Lax',
    )
    @patch('core.auth.cookies._access_max_age', return_value=1800)
    @patch('core.auth.cookies._refresh_max_age', return_value=1209600)
    def test_session_cookies_omit_max_age(self, _mock_ref, _mock_acc):
        response = HttpResponse()
        set_auth_cookies(response, 'access-jwt', 'refresh-opaque', persistent=False)

        access = response.cookies.get('access_client')
        refresh = response.cookies.get('refresh_client')
        self.assertIsNotNone(access)
        self.assertIsNotNone(refresh)
        self.assertTrue(access['httponly'])
        self.assertFalse(access['max-age'])
        self.assertFalse(refresh['max-age'])
        self.assertFalse(access['expires'])
        self.assertFalse(refresh['expires'])


# ── clear_auth_cookies ───────────────────────────────────────────────────────

class TestClearAuthCookies(TestCase):

    @override_settings(DEBUG=True, AUTH_COOKIE_DOMAIN='.base.local')
    def test_clear_client_cookies(self):
        response = HttpResponse()
        clear_auth_cookies(response)

        for name in ['access_client', 'refresh_client']:
            cookie = response.cookies.get(name)
            self.assertIsNotNone(cookie, f'{name} should be cleared')
            self.assertEqual(cookie['max-age'], 0)
            self.assertEqual(cookie['path'], '/')

    @override_settings(DEBUG=True, AUTH_COOKIE_DOMAIN='.base.local')
    def test_clear_admin_cookies(self):
        response = HttpResponse()
        clear_auth_cookies(response, admin=True)

        for name in ['access_admin', 'refresh_admin']:
            cookie = response.cookies.get(name)
            self.assertIsNotNone(cookie, f'{name} should be cleared')
            self.assertEqual(cookie['max-age'], 0)

    @override_settings(DEBUG=True, AUTH_COOKIE_DOMAIN='.base.local')
    def test_clear_also_removes_legacy_cookies(self):
        response = HttpResponse()
        clear_auth_cookies(response)

        for name in ['token_admin', 'token_client']:
            cookie = response.cookies.get(name)
            self.assertIsNotNone(cookie, f'legacy {name} should be cleared')
            self.assertEqual(cookie['max-age'], 0)

    @override_settings(DEBUG=True, AUTH_COOKIE_DOMAIN='.base.local')
    def test_clear_auth_cookies_does_not_drop_device_cookie(self):
        response = HttpResponse()
        set_device_cookie(response, 'a' * 32)
        clear_auth_cookies(response)

        device = response.cookies.get(DEVICE_CLIENT_COOKIE)
        self.assertIsNotNone(device)
        self.assertEqual(device.value, 'a' * 32)
        self.assertNotEqual(device['max-age'], 0)


# ── device_client cookie ────────────────────────────────────────────────────

class TestDeviceClientCookie(TestCase):

    def test_read_accepts_valid_serial(self):
        serial = 'a' * 32
        request = _make_request(cookies={DEVICE_CLIENT_COOKIE: serial})
        self.assertEqual(read_device_serial(request), serial)

    def test_read_rejects_short_serial(self):
        request = _make_request(cookies={DEVICE_CLIENT_COOKIE: 'short'})
        self.assertIsNone(read_device_serial(request))

    def test_read_rejects_invalid_characters(self):
        request = _make_request(cookies={DEVICE_CLIENT_COOKIE: '!!!!-not-valid-xx'})
        self.assertIsNone(read_device_serial(request))

    def test_read_rejects_missing_cookie(self):
        self.assertIsNone(read_device_serial(_make_request()))

    @override_settings(
        DEBUG=True,
        AUTH_COOKIE_DOMAIN='.base.local',
        AUTH_COOKIE_SAMESITE='Lax',
    )
    def test_set_is_httponly_with_90_day_max_age(self):
        response = HttpResponse()
        serial = 'b' * 32
        set_device_cookie(response, serial)

        cookie = response.cookies.get(DEVICE_CLIENT_COOKIE)
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, serial)
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['domain'], '.base.local')
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/')
        self.assertEqual(cookie['max-age'], DEVICE_COOKIE_MAX_AGE)

    @override_settings(DEBUG=False, AUTH_COOKIE_SAMESITE='Lax')
    def test_production_mode_sets_secure(self):
        response = HttpResponse()
        set_device_cookie(response, 'c' * 32)
        self.assertTrue(response.cookies[DEVICE_CLIENT_COOKIE]['secure'])

    @override_settings(DEBUG=True, AUTH_COOKIE_DOMAIN='.base.local')
    def test_clear_expires_device_cookie(self):
        response = HttpResponse()
        clear_device_cookie(response)
        cookie = response.cookies.get(DEVICE_CLIENT_COOKIE)
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie['max-age'], 0)
        self.assertEqual(cookie['path'], '/')


# ── _auth_context helper ────────────────────────────────────────────────────

class TestAuthContextHelper(TestCase):

    def test_returns_none_when_header_missing(self):
        from core.auth.cookie_authentication import _auth_context
        request = _make_request()
        self.assertIsNone(_auth_context(request))

    def test_returns_lowered_value(self):
        from core.auth.cookie_authentication import _auth_context
        request = _make_request(auth_context='Admin')
        self.assertEqual(_auth_context(request), 'admin')

    def test_returns_client(self):
        from core.auth.cookie_authentication import _auth_context
        request = _make_request(auth_context='client')
        self.assertEqual(_auth_context(request), 'client')

    def test_empty_string_returns_none(self):
        from core.auth.cookie_authentication import _auth_context
        request = _make_request(auth_context='')
        self.assertIsNone(_auth_context(request))


# ── JWTAccessAuthentication (client) ─────────────────────────────────────────

class TestJWTAccessAuthentication(TestCase):

    def setUp(self):
        from core.auth.cookie_authentication import JWTAccessAuthentication
        self.auth = JWTAccessAuthentication()

    def test_missing_cookie_returns_none(self):
        request = _make_request()
        self.assertIsNone(self.auth.authenticate(request))

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_expired_token_raises(self, mock_decode):
        import jwt as pyjwt
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.side_effect = pyjwt.ExpiredSignatureError()
        request = _make_request(cookies={'access_client': 'expired-jwt'})

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_invalid_token_raises(self, mock_decode):
        import jwt as pyjwt
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.side_effect = pyjwt.InvalidTokenError()
        request = _make_request(cookies={'access_client': 'bad-jwt'})

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_admin_type_token_returns_none(self, mock_decode):
        mock_decode.return_value = {'user_id': '1', 'user_type': 'admin'}
        request = _make_request(cookies={'access_client': 'admin-jwt-in-client-cookie'})
        self.assertIsNone(self.auth.authenticate(request))

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.reject_idle_client_session', return_value=False)
    @patch('core.auth.cookie_authentication.read_session', return_value={'hash': 'x'})
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_closed_company_still_allows_requests_during_grace(self, mock_decode, _read, _idle):
        mock_user = MagicMock()
        mock_user.company.lifecycle = 'CLOSED'
        mock_decode.return_value = {
            'user_id': 'user-1', 'user_type': 'client', 'sid': 'sess456',
        }

        with patch('django.contrib.auth.get_user_model') as mock_get_model:
            MockUser = MagicMock()
            MockUser.objects.select_related.return_value.get.return_value = mock_user
            mock_get_model.return_value = MockUser
            request = _make_request(cookies={'access_client': 'good-jwt'})
            request.path = '/api/v1/warehouse/orders/'
            result = self.auth.authenticate(request)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], mock_user)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.reject_idle_client_session', return_value=False)
    @patch('core.auth.cookie_authentication.read_session', return_value={'hash': 'x'})
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_gone_company_raises_auth_019(self, mock_decode, _read, _idle):
        from core.errors import AppErrorCode, AuthException

        mock_user = MagicMock()
        mock_user.company.lifecycle = 'GONE'
        mock_decode.return_value = {
            'user_id': 'user-1', 'user_type': 'client', 'sid': 'sess456',
        }

        with patch('django.contrib.auth.get_user_model') as mock_get_model:
            MockUser = MagicMock()
            MockUser.objects.select_related.return_value.get.return_value = mock_user
            mock_get_model.return_value = MockUser
            request = _make_request(cookies={'access_client': 'good-jwt'})
            request.path = '/api/v1/warehouse/orders/'
            with self.assertRaises(AuthException) as ctx:
                self.auth.authenticate(request)
            self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_COMPANY_CLOSED)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.reject_idle_client_session', return_value=False)
    @patch('core.auth.cookie_authentication.read_session', return_value={'hash': 'x'})
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_closed_company_allows_close_complete(self, mock_decode, _read, _idle):
        mock_user = MagicMock()
        mock_user.company.lifecycle = 'CLOSED'
        mock_decode.return_value = {
            'user_id': 'user-1', 'user_type': 'client', 'sid': 'sess456',
        }

        with patch('django.contrib.auth.get_user_model') as mock_get_model:
            MockUser = MagicMock()
            MockUser.objects.select_related.return_value.get.return_value = mock_user
            mock_get_model.return_value = MockUser
            request = _make_request(cookies={'access_client': 'good-jwt'})
            request.path = '/api/v1/companies/id/abc/close/complete/'
            result = self.auth.authenticate(request)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], mock_user)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.reject_idle_client_session', return_value=False)
    @patch('core.auth.cookie_authentication.read_session', return_value={'hash': 'x'})
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_closed_company_allows_logout(self, mock_decode, _read, _idle):
        mock_user = MagicMock()
        mock_user.company.lifecycle = 'GONE'
        mock_decode.return_value = {
            'user_id': 'user-1', 'user_type': 'client', 'sid': 'sess456',
        }

        with patch('django.contrib.auth.get_user_model') as mock_get_model:
            MockUser = MagicMock()
            MockUser.objects.select_related.return_value.get.return_value = mock_user
            mock_get_model.return_value = MockUser
            request = _make_request(cookies={'access_client': 'good-jwt'})
            request.path = '/api/v1/auth/logout/'
            result = self.auth.authenticate(request)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], mock_user)


# ── JWTAdminAccessAuthentication (admin) ─────────────────────────────────────

class TestJWTAdminAccessAuthentication(TestCase):

    def setUp(self):
        from core.auth.cookie_authentication import JWTAdminAccessAuthentication
        self.auth = JWTAdminAccessAuthentication()

    def test_missing_cookie_returns_none(self):
        request = _make_request()
        self.assertIsNone(self.auth.authenticate(request))

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_expired_admin_token_raises(self, mock_decode):
        import jwt as pyjwt
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.side_effect = pyjwt.ExpiredSignatureError()
        request = _make_request(cookies={'access_admin': 'expired-admin-jwt'})

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_client_type_returns_none(self, mock_decode):
        mock_decode.return_value = {'user_id': '1', 'user_type': 'client'}
        request = _make_request(cookies={'access_admin': 'client-jwt-in-admin-cookie'})
        self.assertIsNone(self.auth.authenticate(request))


# ── X-Auth-Context header ───────────────────────────────────────────────────

class TestAuthContextClientSkipsAdminAuth(TestCase):
    """When X-Auth-Context: client, JWTAdminAccessAuthentication must skip."""

    def setUp(self):
        from core.auth.cookie_authentication import JWTAdminAccessAuthentication
        self.auth = JWTAdminAccessAuthentication()

    def test_client_context_skips_admin_auth(self):
        request = _make_request(
            cookies={'access_admin': 'valid-admin-jwt'},
            auth_context='client',
        )
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    def test_no_context_does_not_skip(self):
        """Without X-Auth-Context, admin auth proceeds normally (may fail for other reasons)."""
        request = _make_request(cookies={})
        result = self.auth.authenticate(request)
        self.assertIsNone(result)  # None because no cookie, not because skipped

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.reject_idle_admin_session', return_value=False)
    @patch('core.auth.cookie_authentication.read_session', return_value={'hash': 'x'})
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_admin_context_allows_admin_auth(self, mock_decode, _read, _idle):
        """X-Auth-Context: admin should NOT skip admin auth."""
        mock_user = MagicMock()
        mock_decode.return_value = {
            'user_id': 'admin-1', 'user_type': 'admin', 'sid': 'session123',
        }

        with patch('platform.features.security.identity.users.models.AdminUser') as MockAdminUser:
            MockAdminUser.objects.select_related.return_value.get.return_value = mock_user
            request = _make_request(
                cookies={'access_admin': 'good-jwt'},
                auth_context='admin',
            )
            result = self.auth.authenticate(request)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], mock_user)


class TestAuthContextAdminSkipsClientAuth(TestCase):
    """When X-Auth-Context: admin, JWTAccessAuthentication must skip."""

    def setUp(self):
        from core.auth.cookie_authentication import JWTAccessAuthentication
        self.auth = JWTAccessAuthentication()

    def test_admin_context_skips_client_auth(self):
        request = _make_request(
            cookies={'access_client': 'valid-client-jwt'},
            auth_context='admin',
        )
        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.reject_idle_client_session', return_value=False)
    @patch('core.auth.cookie_authentication.read_session', return_value={'hash': 'x'})
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_client_context_allows_client_auth(self, mock_decode, _read, _idle):
        """X-Auth-Context: client should NOT skip client auth."""
        mock_user = MagicMock()
        mock_decode.return_value = {
            'user_id': 'user-1', 'user_type': 'client', 'sid': 'sess456',
        }

        with patch('django.contrib.auth.get_user_model') as mock_get_model:
            MockUser = MagicMock()
            MockUser.objects.select_related.return_value.get.return_value = mock_user
            mock_get_model.return_value = MockUser
            request = _make_request(
                cookies={'access_client': 'good-jwt'},
                auth_context='client',
            )
            result = self.auth.authenticate(request)
            self.assertIsNotNone(result)
            self.assertEqual(result[0], mock_user)


class TestAuthContextBothCookiesPresent(TestCase):
    """Scenario: browser has both admin and client cookies (same person, two apps).

    The X-Auth-Context header determines which authentication class runs.
    The other class must return None so DRF skips it cleanly.
    """

    def test_client_context_skips_admin_even_with_valid_admin_cookie(self):
        from core.auth.cookie_authentication import JWTAdminAccessAuthentication
        auth = JWTAdminAccessAuthentication()

        request = _make_request(
            cookies={
                'access_admin': 'valid-admin-jwt',
                'access_client': 'valid-client-jwt',
            },
            auth_context='client',
        )
        result = auth.authenticate(request)
        self.assertIsNone(result)

    def test_admin_context_skips_client_even_with_valid_client_cookie(self):
        from core.auth.cookie_authentication import JWTAccessAuthentication
        auth = JWTAccessAuthentication()

        request = _make_request(
            cookies={
                'access_admin': 'valid-admin-jwt',
                'access_client': 'valid-client-jwt',
            },
            auth_context='admin',
        )
        result = auth.authenticate(request)
        self.assertIsNone(result)


# ── Session id (sid) in JWT ──────────────────────────────────────────────────

class TestSessionIdInJWT(TestCase):
    """Verify that create_access_token embeds 'sid' and decode returns it."""

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_sid_embedded_in_token(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(
            user_id='u1',
            user_type='client',
            schema_name='tenant_acme',
            session_id='abc123def4567890',
        )
        payload = decode_access_token(token)
        self.assertEqual(payload['sid'], 'abc123def4567890')

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_sid_defaults_to_empty_string(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(user_id='u1', user_type='client')
        payload = decode_access_token(token)
        self.assertEqual(payload['sid'], '')


# ── Session kill effectiveness ───────────────────────────────────────────────

class TestSessionKillBlocksAccess(TestCase):
    """After a session is killed (refresh token removed from Redis), the
    access token must be rejected even if its JWT signature is still valid."""

    def setUp(self):
        from core.auth.cookie_authentication import JWTAccessAuthentication
        self.auth = JWTAccessAuthentication()

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.reject_idle_client_session', return_value=False)
    @patch('core.auth.cookie_authentication.read_session', return_value={'hash': 'x'})
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_valid_session_authenticates(self, mock_decode, mock_read, mock_idle):
        """Baseline: when session exists, authentication succeeds."""
        mock_user = MagicMock()
        mock_decode.return_value = {
            'user_id': 'u1', 'user_type': 'client', 'sid': 'sess_abc',
        }

        with patch('django.contrib.auth.get_user_model') as mock_get_model:
            MockUser = MagicMock()
            MockUser.objects.select_related.return_value.get.return_value = mock_user
            mock_get_model.return_value = MockUser
            request = _make_request(cookies={'access_client': 'good-jwt'})
            result = self.auth.authenticate(request)
            self.assertIsNotNone(result)

        mock_read.assert_called_once_with('client', 'u1', 'sess_abc')
        mock_idle.assert_called_once_with('u1', 'sess_abc', record={'hash': 'x'})

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.reject_idle_client_session', return_value=True)
    @patch('core.auth.cookie_authentication.read_session', return_value={'hash': 'x'})
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_idle_session_raises_auth_020(self, mock_decode, _read, _idle):
        from core.errors import AppErrorCode, AuthException

        mock_decode.return_value = {
            'user_id': 'u1', 'user_type': 'client', 'sid': 'sess_abc',
        }
        request = _make_request(cookies={'access_client': 'good-jwt'})
        with self.assertRaises(AuthException) as ctx:
            self.auth.authenticate(request)
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_SESSION_IDLE)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.read_session', return_value=None)
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_killed_session_raises(self, mock_decode, mock_read):
        """After session kill, read_session returns None → AuthenticationFailed."""
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.return_value = {
            'user_id': 'u1', 'user_type': 'client', 'sid': 'sess_abc',
        }
        request = _make_request(cookies={'access_client': 'good-jwt'})

        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)

        self.assertIn('revoked', str(ctx.exception.detail).lower())

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_legacy_token_without_sid_raises(self, mock_decode):
        """Tokens generated before the sid change (no sid) must be rejected."""
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.return_value = {
            'user_id': 'u1', 'user_type': 'client',
            # No 'sid' key at all — legacy token
        }
        request = _make_request(cookies={'access_client': 'legacy-jwt'})

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_empty_sid_raises(self, mock_decode):
        """Token with sid='' must also be rejected (forces refresh)."""
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.return_value = {
            'user_id': 'u1', 'user_type': 'client', 'sid': '',
        }
        request = _make_request(cookies={'access_client': 'empty-sid-jwt'})

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)


class TestRefreshTokenIdle(TestCase):

    def setUp(self):
        from core.auth.cookie_authentication import RefreshTokenAuthentication
        self.auth = RefreshTokenAuthentication()

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.refresh_service.revoke')
    @patch('core.auth.cookie_authentication.session_record_is_idle', return_value=True)
    @patch('core.auth.cookie_authentication.refresh_service.validate')
    def test_idle_refresh_revokes_and_raises_auth_020(self, mock_validate, _idle, mock_revoke):
        from core.errors import AppErrorCode, AuthException

        mock_validate.return_value = {
            'user_id': 'u1', 'user_type': 'client', 'last_activity_at': '2000-01-01T00:00:00',
        }
        request = _make_request(cookies={'refresh_client': 'raw-refresh'})
        with self.assertRaises(AuthException) as ctx:
            self.auth.authenticate(request)
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_SESSION_IDLE)
        mock_revoke.assert_called_once_with('raw-refresh', user_type='client')


class TestAdminSessionKillBlocksAccess(TestCase):
    """Same as TestSessionKillBlocksAccess but for admin authentication."""

    def setUp(self):
        from core.auth.cookie_authentication import JWTAdminAccessAuthentication
        self.auth = JWTAdminAccessAuthentication()

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.read_session', return_value=None)
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_killed_admin_session_raises(self, mock_decode, mock_read):
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.return_value = {
            'user_id': 'a1', 'user_type': 'admin', 'sid': 'admin_sess',
        }
        request = _make_request(cookies={'access_admin': 'good-admin-jwt'})

        with self.assertRaises(AuthenticationFailed) as ctx:
            self.auth.authenticate(request)

        self.assertIn('revoked', str(ctx.exception.detail).lower())
        mock_read.assert_called_once_with('admin', 'a1', 'admin_sess')

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_admin_legacy_token_without_sid_raises(self, mock_decode):
        from rest_framework.exceptions import AuthenticationFailed

        mock_decode.return_value = {'user_id': 'a1', 'user_type': 'admin'}
        request = _make_request(cookies={'access_admin': 'legacy-admin-jwt'})

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)


class TestClientUserLoadedOnce(TestCase):

    @patch('django.contrib.auth.get_user_model')
    def test_second_lookup_reuses_the_request_user(self, mock_get_model):
        from core.auth.cookie_authentication import get_client_user

        user = MagicMock()
        user.company_id = 'company-1'
        MockUser = MagicMock()
        MockUser.objects.select_related.return_value.get.return_value = user
        mock_get_model.return_value = MockUser
        request = SimpleNamespace()

        first = get_client_user(request, 'user-1')
        second = get_client_user(request, 'user-1')

        self.assertIs(first, user)
        self.assertIs(second, user)
        MockUser.objects.select_related.return_value.get.assert_called_once()


# ── Cross-context session kill (the real bug scenario) ───────────────────────

class TestCrossContextSessionKill(TestCase):
    """Reproduces the exact bug: admin kills a client session, but the
    client web still had both cookies.  Without X-Auth-Context the admin
    cookie would authenticate the request.  With the header, the admin
    cookie is skipped and the revoked client session is correctly rejected.
    """

    @override_settings(SECRET_KEY='test-secret')
    @patch('core.auth.cookie_authentication.read_session', return_value=None)
    @patch('core.auth.cookie_authentication.decode_access_token')
    def test_client_context_rejects_after_session_kill(self, mock_decode, _read):
        """Client web sends X-Auth-Context: client.  Client session was killed.
        Even though a valid access_admin cookie is present, it must NOT be used.
        """
        from rest_framework.exceptions import AuthenticationFailed
        from core.auth.cookie_authentication import (
            JWTAdminAccessAuthentication,
            JWTAccessAuthentication,
        )

        mock_decode.return_value = {
            'user_id': 'u1', 'user_type': 'client', 'sid': 'killed_sess',
        }

        request = _make_request(
            cookies={
                'access_admin': 'valid-admin-jwt',
                'access_client': 'client-jwt-with-killed-session',
            },
            auth_context='client',
        )

        # Admin auth: must skip because context is 'client'
        admin_auth = JWTAdminAccessAuthentication()
        self.assertIsNone(admin_auth.authenticate(request))

        # Client auth: must reject because session was killed
        client_auth = JWTAccessAuthentication()
        with self.assertRaises(AuthenticationFailed):
            client_auth.authenticate(request)
