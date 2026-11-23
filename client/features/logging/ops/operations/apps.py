from django.apps import AppConfig


class OperationsLogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.logging.ops.operations'
    label = 'logging_operations'
