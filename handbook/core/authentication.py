"""Autenticación dual (admin o cliente) para APIs del handbook en host público.

Reutiliza las cookies HttpOnly existentes. El JWT de cliente trae
``schema_name``: el usuario tenant se carga dentro de ese schema para que
las vistas del handbook no tengan que vivir en el URLconf del tenant.
"""

from __future__ import annotations

import jwt as pyjwt
from django.db import connection
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.auth.cookie_authentication import JWTAccessAuthentication, JWTAdminAccessAuthentication
from core.auth.cookies import ACCESS_CLIENT_COOKIE
from core.auth.jwt_service import decode_access_token
from core.auth.refresh_service import session_exists
from core.errors import AuthException


def _auth_context(request) -> str | None:
    value = request.META.get('HTTP_X_AUTH_CONTEXT', '')
    return value.lower() or None


class HandbookAccessAuthentication(BaseAuthentication):
    """Admin (``access_admin``) o cliente (``access_client``). Sin cookie → anónimo.

    Sin ``X-Auth-Context`` el lector se declara anónimo: una cookie vencida o
    revocada que quedó en el navegador no bloquea el handbook público.
    Con contexto declarado se mantiene el 401 para que el frontend refresque.
    """

    def authenticate(self, request):
        context = _auth_context(request)
        if context == 'admin':
            return JWTAdminAccessAuthentication().authenticate(request)
        if context == 'client':
            return self._authenticate_client(request)

        for attempt in (JWTAdminAccessAuthentication().authenticate, self._authenticate_client):
            try:
                result = attempt(request)
            except (AuthenticationFailed, AuthException):
                continue
            if result is not None:
                return result
        return None

    def _authenticate_client(self, request):
        token = request.COOKIES.get(ACCESS_CLIENT_COOKIE)
        if not token:
            return None
        try:
            payload = decode_access_token(token)
        except pyjwt.ExpiredSignatureError:
            raise AuthenticationFailed('Session expired.')
        except pyjwt.InvalidTokenError:
            raise AuthenticationFailed('Invalid session.')

        if payload.get('user_type') != 'client':
            return None

        sid = payload.get('sid')
        if not sid or not session_exists('client', payload['user_id'], sid):
            raise AuthenticationFailed('Session revoked.')

        schema_name = payload.get('schema_name') or ''
        if not schema_name or schema_name in ('public', getattr(connection, 'schema_name', None)):
            # Login desde el host público emite ``schema_name='public'``; el
            # usuario vive en el schema compartido y se carga en la conexión actual.
            return JWTAccessAuthentication().authenticate(request)

        from django.contrib.auth import get_user_model
        from django_tenants.utils import schema_context

        User = get_user_model()
        with schema_context(schema_name):
            try:
                user = User.objects.select_related('rol', 'company').get(
                    pk=payload['user_id'], is_active=True,
                )
            except User.DoesNotExist:
                raise AuthenticationFailed('User not found or inactive.')

        return user, payload
