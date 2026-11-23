from django.apps import AppConfig


class AdminParameterTypeAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.configuration.admin_parameters.admin_parameter_type'
    label = 'admin_parameter_type'
    verbose_name = 'Admin parameter types'
