from django.apps import AppConfig


class LogConfigAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.logging.system.config'
    label = 'logging_config'
