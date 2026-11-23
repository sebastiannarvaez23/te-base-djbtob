"""
ASGI config for the base project.

Sirve dos protocolos:
  - http      → la app ASGI estándar de Django (toda la API REST).
  - websocket → Django Channels, con autenticación por cookie JWT y
                resolución de tenant antes de llegar al consumidor.

La pila de middlewares WS replica el modelo de la API HTTP:
  CookieMiddleware → puebla scope['cookies'] desde el handshake.
  JWTAuthMiddleware → resuelve scope['user'] / scope['audience'].
  TenantContextMiddleware → resuelve scope['tenant_schema'].
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings.local')

# Inicializa Django (apps, settings) ANTES de importar consumidores/rutas
# que cargan modelos.
django_asgi_app = get_asgi_application()

from platform.features.support.ops.live_logs.infrastructure.stream_attach import (  # noqa: E402
    attach_live_log_handlers,
)

attach_live_log_handlers()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.sessions import CookieMiddleware  # noqa: E402

from core.realtime.auth import JWTAuthMiddleware  # noqa: E402
from core.realtime.tenant import TenantContextMiddleware  # noqa: E402

from client.features.communication.messaging.inbox.realtime.routing import (  # noqa: E402
    websocket_urlpatterns as inbox_ws_patterns,
)
from client.features.communication.assistant.chat.realtime.routing import (  # noqa: E402
    websocket_urlpatterns as assistant_ws_patterns,
)
from platform.features.support.ops.task_monitor.presentation.realtime.routing import (  # noqa: E402
    websocket_urlpatterns as task_monitor_ws_patterns,
)
from platform.features.support.ops.live_logs.presentation.realtime.routing import (  # noqa: E402
    websocket_urlpatterns as live_logs_ws_patterns,
)
from platform.features.communication.messaging.inbox.presentation.realtime.routing import (  # noqa: E402
    websocket_urlpatterns as admin_inbox_ws_patterns,
)
from platform.features.support.sessions.session.presentation.realtime.routing import (  # noqa: E402
    websocket_urlpatterns as support_session_ws_patterns,
)

websocket_urlpatterns = [
    *inbox_ws_patterns,
    *assistant_ws_patterns,
    *task_monitor_ws_patterns,
    *live_logs_ws_patterns,
    *admin_inbox_ws_patterns,
    *support_session_ws_patterns,
]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': CookieMiddleware(
        JWTAuthMiddleware(
            TenantContextMiddleware(
                URLRouter(websocket_urlpatterns)
            )
        )
    ),
})
