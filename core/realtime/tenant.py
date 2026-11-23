"""
core/realtime/tenant.py
───────────────────────
Middleware ASGI que resuelve el schema del tenant para la conexión WS.

Channels no corre los middlewares de django-tenants, así que el schema se
deriva de forma determinista del usuario autenticado (cada usuario
pertenece a una sola empresa) y queda en ``scope['tenant_schema']``.

Para audiencia ``admin`` el schema es siempre ``public``.
"""

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware


class TenantContextMiddleware(BaseMiddleware):
    """Inyecta ``scope['tenant_schema']`` a partir de ``scope['user']`` / audience."""

    async def __call__(self, scope, receive, send):
        scope['tenant_schema'] = await self._resolve(
            scope.get('user'), scope.get('audience'),
        )
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def _resolve(self, user, audience):
        if user is None:
            return None
        if audience == 'admin':
            return 'public'
        try:
            return user.company.schema_name
        except Exception:
            return None
