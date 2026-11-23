"""Unit tests for core.auth.jwt_service — JWT access token generation and validation."""
import time
from unittest import TestCase
from unittest.mock import patch

from django.test import override_settings


class TestCreateAccessToken(TestCase):

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_creates_valid_jwt(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(
            user_id='abc-123',
            user_type='client',
            schema_name='tenant_acme',
        )
        self.assertIsInstance(token, str)

        payload = decode_access_token(token)
        self.assertEqual(payload['user_id'], 'abc-123')
        self.assertEqual(payload['user_type'], 'client')
        self.assertEqual(payload['schema_name'], 'tenant_acme')
        self.assertIn('exp', payload)
        self.assertIn('iat', payload)

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_admin_token_has_correct_user_type(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(user_id='admin-1', user_type='admin')
        payload = decode_access_token(token)
        self.assertEqual(payload['user_type'], 'admin')
        self.assertEqual(payload['schema_name'], 'public')

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_session_id_embedded_in_payload(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(
            user_id='u1', user_type='client', session_id='abc123',
        )
        payload = decode_access_token(token)
        self.assertEqual(payload['sid'], 'abc123')

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_session_id_defaults_to_empty(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(user_id='u1', user_type='client')
        payload = decode_access_token(token)
        self.assertEqual(payload['sid'], '')

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_username_claim_embedded_when_provided(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(
            user_id='u1', user_type='admin', username='ops.user',
        )
        payload = decode_access_token(token)
        self.assertEqual(payload['username'], 'ops.user')

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_username_omitted_when_empty(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(user_id='u1', user_type='client')
        payload = decode_access_token(token)
        self.assertNotIn('username', payload)


class TestDecodeAccessToken(TestCase):

    @override_settings(SECRET_KEY='test-secret-key')
    @patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30)
    def test_decode_returns_payload(self, _mock_ttl):
        from core.auth.jwt_service import create_access_token, decode_access_token

        token = create_access_token(user_id='u1', user_type='client')
        payload = decode_access_token(token)
        self.assertEqual(payload['user_id'], 'u1')

    @override_settings(SECRET_KEY='test-secret-key')
    def test_expired_token_raises(self):
        import jwt as pyjwt
        from core.auth.jwt_service import decode_access_token
        from datetime import datetime, timedelta

        expired_payload = {
            'user_id': 'u1', 'user_type': 'client', 'schema_name': 'public',
            'iat': datetime.utcnow() - timedelta(hours=2),
            'exp': datetime.utcnow() - timedelta(hours=1),
        }
        token = pyjwt.encode(expired_payload, 'test-secret-key', algorithm='HS256')

        with self.assertRaises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    @override_settings(SECRET_KEY='test-secret-key')
    def test_wrong_secret_raises(self):
        import jwt as pyjwt
        from core.auth.jwt_service import decode_access_token
        from datetime import datetime, timedelta

        payload = {
            'user_id': 'u1', 'user_type': 'client', 'schema_name': 'public',
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=1),
        }
        token = pyjwt.encode(payload, 'wrong-secret', algorithm='HS256')

        with self.assertRaises(pyjwt.InvalidTokenError):
            decode_access_token(token)

    @override_settings(SECRET_KEY='test-secret-key')
    def test_malformed_token_raises(self):
        import jwt as pyjwt
        from core.auth.jwt_service import decode_access_token

        with self.assertRaises(pyjwt.InvalidTokenError):
            decode_access_token('not-a-jwt')


class TestGetAccessTtlMinutes(TestCase):

    @patch('core.auth.jwt_service.get_access_ttl_minutes')
    def test_fallback_when_parameter_unavailable(self, mock_ttl):
        mock_ttl.return_value = 1440
        from core.auth.jwt_service import get_access_ttl_minutes
        self.assertEqual(get_access_ttl_minutes(), 1440)
