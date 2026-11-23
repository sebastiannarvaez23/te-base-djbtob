from django.apps import AppConfig


class ParameterTypeAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.configuration.parameters.parameter_type'
    label = 'parameter_type'
    verbose_name = 'Parameter types'
