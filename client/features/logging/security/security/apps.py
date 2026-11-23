from django.apps import AppConfig


class SecurityLogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.logging.security.security'
    label = 'logging_security'
