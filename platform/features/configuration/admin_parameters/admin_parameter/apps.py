from django.apps import AppConfig


class AdminParameterAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.configuration.admin_parameters.admin_parameter'
    label = 'admin_parameter'
    verbose_name = 'Admin parameters'
