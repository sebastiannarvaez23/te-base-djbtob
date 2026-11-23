from django.apps import AppConfig


class IntegrationLogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.logging.ops.integration'
    label = 'logging_integration'
