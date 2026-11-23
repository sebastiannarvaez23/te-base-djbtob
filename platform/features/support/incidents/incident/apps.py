from django.apps import AppConfig


class SupportIncidentAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.support.incidents.incident'
    label = 'support_incident'

    def ready(self):
        # Wire the Celery BaseTask incident hook without core importing platform.
        from core.tasks.incident_port import set_task_incident_reporter
        from platform.features.support.incidents.incident.integration import (
            report_automated_task_failure,
        )

        set_task_incident_reporter(report_automated_task_failure)
