from django.apps import AppConfig


class SupportTaskMonitorAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.support.ops.task_monitor'
    label = 'support_task_monitor'

    def ready(self):
        from core.tasks.progress_port import set_task_progress_reporter
        from platform.features.support.ops.task_monitor.infrastructure.failure_notifier import (
            AdminInboxTaskFailureNotifier,
        )
        from platform.features.support.ops.task_monitor.infrastructure.reporter import (
            DjangoTaskProgressReporter,
        )

        set_task_progress_reporter(DjangoTaskProgressReporter(
            failure_notifier=AdminInboxTaskFailureNotifier(),
        ))
