"""
WSGI config for the base project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings.local')

application = get_wsgi_application()

# runserver reconfigura el logging al cargar esta app y borra el handler
# que AppConfig.ready() había enganchado. Reinstalarlo aquí, después.
from platform.features.support.ops.live_logs.infrastructure.stream_attach import (  # noqa: E402
    attach_live_log_handlers,
)

attach_live_log_handlers()
