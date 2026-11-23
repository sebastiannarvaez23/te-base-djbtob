from django.apps import AppConfig


class AnalyticsCtlAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.analytics.control.ctl'
    label = 'analytics_ctl'
    verbose_name = 'Analytics control plane (wadw)'
