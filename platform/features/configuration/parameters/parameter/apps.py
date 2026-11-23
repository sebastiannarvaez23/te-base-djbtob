from django.apps import AppConfig


class ParameterAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.configuration.parameters.parameter'
    label = 'parameter'
    verbose_name = 'Parameters'
