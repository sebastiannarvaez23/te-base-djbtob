"""
core/realtime/auth.py
─────────────────────
Middleware ASGI que autentica la conexión WebSocket reutilizando el mismo
esquema de la API HTTP: el access token JWT vive en cookie HttpOnly.

Soporta dos audiencias:
  - admin  → cookie ``access_admin`` + ``user_type=admin`` (AdminUser)
  - client → cookie ``access_client`` + ``user_type=client`` (tenant User)

Debe envolverse con ``channels.sessions.CookieMiddleware`` para que
``scope['cookies']`` esté poblado (ver ``base/asgi.py``).
"""

import logging

import jwt as pyjwt
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from core.auth.cookies import ACCESS_ADMIN_COOKIE, ACCESS_CLIENT_COOKIE
from core.auth.jwt_service import decode_access_token
from core.auth.refresh_service import session_exists

logger = logging.getLogger('app.api')


class JWTAuthMiddleware(BaseMiddleware):
    """Resuelve ``scope['user']`` y ``scope['audience']`` desde cookies JWT."""

    async def __call__(self, scope, receive, send):
        user, audience = await self._authenticate(scope)
        scope['user'] = user
        scope['audience'] = audience
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def _authenticate(self, scope):
        cookies = scope.get('cookies') or {}
        path = scope.get('path') or ''

        # Platform WS endpoints require the admin cookie; tenant endpoints
        # prefer the client cookie so dual-login browsers keep working.
        prefer_admin = path.startswith('/ws/platform/')

        if prefer_admin:
            admin_token = cookies.get(ACCESS_ADMIN_COOKIE)
            if admin_token:
                admin = self._authenticate_admin(admin_token)
                if admin is not None:
                    return admin, 'admin'
            return None, None

        client_token = cookies.get(ACCESS_CLIENT_COOKIE)
        if client_token:
            client = self._authenticate_client(client_token)
            if client is not None:
                return client, 'client'

        admin_token = cookies.get(ACCESS_ADMIN_COOKIE)
        if admin_token:
            admin = self._authenticate_admin(admin_token)
            if admin is not None:
                return admin, 'admin'

        return None, None

    def _authenticate_admin(self, token):
        try:
            payload = decode_access_token(token)
        except pyjwt.InvalidTokenError:
            return None

        if payload.get('user_type') != 'admin':
            return None

        sid = payload.get('sid')
        if not sid or not session_exists('admin', payload['user_id'], sid):
            return None

        from platform.features.security.identity.users.models import AdminUser
        try:
            return AdminUser.objects.select_related('role').get(
                pk=payload['user_id'], is_active=True,
            )
        except AdminUser.DoesNotExist:
            return None

    def _authenticate_client(self, token):
        try:
            payload = decode_access_token(token)
        except pyjwt.InvalidTokenError:
            return None

        if payload.get('user_type') != 'client':
            return None

        sid = payload.get('sid')
        if not sid or not session_exists('client', payload['user_id'], sid):
            return None

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.select_related('company').get(
                pk=payload['user_id'], is_active=True,
            )
        except User.DoesNotExist:
            return None
