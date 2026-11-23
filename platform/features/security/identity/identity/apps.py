import os
import sys

from django.apps import AppConfig


class PlatformIdentityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.security.identity.identity'
    label = 'platform_identity'

    def ready(self) -> None:
        if any(cmd in sys.argv for cmd in ('migrate', 'makemigrations', 'test', 'collectstatic')):
            return

        # Autoreloader parent loads AppConfig too; skip so MinIO is not
        # bootstrapped twice. ``--noreload`` has no RUN_MAIN and must still run.
        if (
            ('runserver' in sys.argv or 'runserver_plus' in sys.argv)
            and '--noreload' not in sys.argv
            and os.environ.get('RUN_MAIN') != 'true'
        ):
            return

        try:
            from platform.features.security.identity.identity.infrastructure.profile_storage import ensure_profile_storage
            ensure_profile_storage()
        except Exception as exc:
            import logging
            logging.getLogger('app.api').warning(
                'Could not ensure admin profile storage on startup: %s', exc,
            )
