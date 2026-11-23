"""
core/realtime/consumers.py
──────────────────────────
``BaseRealtimeConsumer``: la clase que contiene TODO el comportamiento WS
configurado (auth, tenant, manejo de grupos, reenvío del sobre estándar).

Para usar WebSockets en otro recurso solo se subclasea y se declara
``get_groups()`` — la base no se modifica (Open/Closed):

    class ChatConsumer(BaseRealtimeConsumer):
        def get_groups(self):
            return [RealtimeGroups.company(self.schema)]
"""

import logging

from channels.generic.websocket import AsyncJsonWebsocketConsumer

logger = logging.getLogger('app.api')


class BaseRealtimeConsumer(AsyncJsonWebsocketConsumer):
    """Base reutilizable para cualquier recurso en tiempo real.

    El ``user`` y el ``tenant_schema`` los inyectan los middlewares ASGI
    (``JWTAuthMiddleware`` + ``TenantContextMiddleware``) antes de llegar
    aquí. El consumidor no lleva lógica de negocio: solo une grupos y
    reenvía lo que el ``RealtimePublisher`` haya empujado.
    """

    async def connect(self):
        self.user = self.scope.get('user')
        self.schema = self.scope.get('tenant_schema')

        if self.user is None or self.schema is None:
            # 4401 = unauthorized (rango privado de cierre de WS).
            await self.close(code=4401)
            return

        self.groups_joined = self.get_groups()
        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        for group in getattr(self, 'groups_joined', []):
            await self.channel_layer.group_discard(group, self.channel_name)

    # ── Salida: el channel layer entrega aquí lo que publique el publisher ──
    async def realtime_message(self, event):
        """Handler de los mensajes con ``type='realtime.message'``."""
        await self.send_json(event['payload'])

    # ── Contrato para subclases ─────────────────────────────────────────────
    def get_groups(self) -> list[str]:
        """Grupos que esta conexión debe escuchar. Override obligatorio."""
        raise NotImplementedError
