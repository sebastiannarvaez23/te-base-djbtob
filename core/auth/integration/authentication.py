"""DRF authentication via ``Authorization: Bearer`` for Integration Apps."""
from __future__ import annotations

import logging

import jwt as pyjwt
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.auth.integration.jwt_service import (
    INTEGRATION_USER_TYPE,
    decode_integration_access_token,
)
from core.auth.integration.principal import IntegrationPrincipal

logger = logging.getLogger('app.auth.integration')


class IntegrationBearerAuthentication(BaseAuthentication):
    """Authenticate external apps with an integration JWT Bearer token.

    Rejects human (admin/client) tokens even if presented as Bearer.
    Loads the application row to enforce ACTIVE status (immediate revoke).
    """

    keyword = 'Bearer'

    def authenticate(self, request):
        header = self._get_authorization_header(request)
        if header is None:
            return None

        token = self._extract_bearer(header)
        if token is None:
            return None

        try:
            payload = decode_integration_access_token(token)
        except pyjwt.ExpiredSignatureError:
            raise AuthenticationFailed('Integration access token expired.')
        except pyjwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid integration access token.')

        if payload.get('user_type') != INTEGRATION_USER_TYPE:
            raise AuthenticationFailed('Token is not an integration credential.')

        app_id = payload.get('app_id')
        if not app_id:
            raise AuthenticationFailed('Integration token missing app_id.')

        app = self._load_active_app(app_id)
        if app is None:
            raise AuthenticationFailed('Integration application is inactive or unknown.')

        token_schema = payload.get('schema_name') or ''
        # Best-effort tenant binding when the request already resolved a schema.
        try:
            from django.db import connection
            current = getattr(connection, 'schema_name', None)
            if current and token_schema and current not in ('public',) and current != token_schema:
                raise AuthenticationFailed('Integration token tenant mismatch.')
        except AuthenticationFailed:
            raise
        except Exception:
            logger.debug('Could not verify schema_name for integration token', exc_info=True)

        principal = IntegrationPrincipal(
            app_id=str(app.id),
            client_id=app.client_id,
            schema_name=token_schema,
            scopes=payload.get('scopes') or [],
            jti=payload.get('jti') or '',
            name=getattr(app, 'name', '') or '',
        )
        return principal, payload

    def authenticate_header(self, request):
        return self.keyword

    @staticmethod
    def _get_authorization_header(request) -> str | None:
        raw = request.META.get('HTTP_AUTHORIZATION')
        if not raw:
            return None
        return raw

    def _extract_bearer(self, header: str) -> str | None:
        parts = header.split()
        if len(parts) != 2:
            return None
        if parts[0] != self.keyword:
            return None
        return parts[1].strip() or None

    @staticmethod
    def _load_active_app(app_id):
        from client.features.integrations.oauth.client.models import (
            IntegrationApplication,
            IntegrationApplicationStatus,
        )
        try:
            return IntegrationApplication.objects.only(
                'id', 'client_id', 'name', 'status',
            ).get(pk=app_id, status=IntegrationApplicationStatus.ACTIVE)
        except IntegrationApplication.DoesNotExist:
            return None
        except Exception:
            logger.warning('Failed loading integration application %s', app_id, exc_info=True)
            return None
