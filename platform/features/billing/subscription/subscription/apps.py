import os
import sys

from django.apps import AppConfig


class SubscriptionAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.subscription.subscription'
    label = 'subscription'
    verbose_name = "Suscripción"

    def ready(self):
        # Inversión de dependencia: registramos el handler de expiración con el
        # hook de core/access (en vez de que core importe nuestras tareas). Es
        # barato e idempotente, así que se registra siempre.
        from core.access.hooks import register_subscription_expiry_handler
        from .integration.expiry_hook import on_subscription_expiry
        register_subscription_expiry_handler(on_subscription_expiry)

        # Solo ejecutar warmup cuando se levanta el servidor,
        # no durante migrate, makemigrations, collectstatic, etc.
        if not self._is_server_running():
            return

        from core.access.warmup import (
            ensure_blank_line_after_runserver_banner,
            warmup_subscription_cache,
        )

        # Patch before Daphne prints the quit banner (both reloader processes).
        ensure_blank_line_after_runserver_banner()

        # RUN_MAIN='true' solo existe en el proceso hijo del auto-reloader.
        # Sin este check, ready() se ejecuta dos veces en runserver.
        if os.environ.get('RUN_MAIN') != 'true':
            return

        warmup_subscription_cache()

    @staticmethod
    def _is_server_running() -> bool:
        """Detecta si Django está arrancando como servidor (runserver/gunicorn/uvicorn)."""
        # runserver, gunicorn, uvicorn, daphne, etc.
        for arg in sys.argv:
            if arg in ('runserver', 'runserver_plus'):
                return True
            if 'gunicorn' in arg or 'uvicorn' in arg or 'daphne' in arg:
                return True
        return False
