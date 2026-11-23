"""Unit tests — integration JWT service."""

from datetime import datetime, timedelta
from unittest.mock import patch

import jwt as pyjwt
import pytest
from django.test import override_settings

from core.auth.integration.jwt_service import (
    INTEGRATION_AUDIENCE,
    INTEGRATION_USER_TYPE,
    create_integration_access_token,
    decode_integration_access_token,
    get_integration_access_ttl_seconds,
    normalize_scopes,
)


@pytest.mark.unit
class TestIntegrationJwtService:

    def test_create_and_decode(self):
        with override_settings(
            SECRET_KEY='human-secret',
            INTEGRATION_JWT_SECRET='integration-secret',
        ), patch(
            'core.auth.integration.jwt_service.get_integration_access_ttl_seconds',
            return_value=600,
        ):
            token, payload = create_integration_access_token(
                app_id='app-1',
                client_id='wa_abc',
                schema_name='tenant_x',
                scopes=['orders:read'],
            )
            decoded = decode_integration_access_token(token)
        assert decoded['user_type'] == INTEGRATION_USER_TYPE
        assert decoded['aud'] == INTEGRATION_AUDIENCE
        assert decoded['app_id'] == 'app-1'
        assert decoded['client_id'] == 'wa_abc'
        assert decoded['scopes'] == ['orders:read']
        assert decoded['schema_name'] == 'tenant_x'
        assert 'jti' in decoded
        assert payload['exp']

    def test_wrong_secret_rejected(self):
        with override_settings(INTEGRATION_JWT_SECRET='integration-secret'):
            token, _ = create_integration_access_token(
                app_id='a', client_id='c', schema_name='t', scopes=[],
            )
        with override_settings(INTEGRATION_JWT_SECRET='other-secret'):
            with pytest.raises(pyjwt.InvalidTokenError):
                decode_integration_access_token(token)

    def test_human_secret_cannot_forge_integration_token(self):
        now = datetime.utcnow()
        forged = pyjwt.encode(
            {
                'user_type': INTEGRATION_USER_TYPE,
                'aud': INTEGRATION_AUDIENCE,
                'app_id': 'x',
                'client_id': 'wa_x',
                'schema_name': 't',
                'scopes': [],
                'jti': '1',
                'iat': now,
                'exp': now + timedelta(hours=1),
            },
            'human-secret',
            algorithm='HS256',
        )
        with override_settings(
            SECRET_KEY='human-secret',
            INTEGRATION_JWT_SECRET='integration-secret',
        ):
            with pytest.raises(pyjwt.InvalidTokenError):
                decode_integration_access_token(forged)

    def test_expired_token_raises(self):
        now = datetime.utcnow()
        token = pyjwt.encode(
            {
                'user_type': INTEGRATION_USER_TYPE,
                'aud': INTEGRATION_AUDIENCE,
                'app_id': 'x',
                'client_id': 'wa_x',
                'schema_name': 't',
                'scopes': [],
                'jti': '1',
                'iat': now - timedelta(hours=2),
                'exp': now - timedelta(hours=1),
            },
            'integration-secret',
            algorithm='HS256',
        )
        with override_settings(INTEGRATION_JWT_SECRET='integration-secret'):
            with pytest.raises(pyjwt.ExpiredSignatureError):
                decode_integration_access_token(token)

    def test_normalize_scopes(self):
        assert normalize_scopes(['b', 'a', 'a', '']) == ['a', 'b']
        assert normalize_scopes(None) == []

    def test_ttl_from_settings(self):
        with override_settings(INTEGRATION_TOKEN_TTL_SECONDS=120):
            assert get_integration_access_ttl_seconds() == 120
