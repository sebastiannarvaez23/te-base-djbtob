from django.apps import AppConfig


class SupportLiveLogsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.support.ops.live_logs'
    label = 'support_live_logs'
    default = True

    def ready(self):
        from django.conf import settings

        if not getattr(settings, 'LIVE_LOGS_ENABLED', True):
            return

        from platform.features.support.ops.live_logs.infrastructure.stream_attach import (
            attach_live_log_handlers,
        )

        attach_live_log_handlers()
