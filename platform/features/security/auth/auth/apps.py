from django.apps import AppConfig


class PlatformAuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.security.auth.auth'
    label = 'platform_auth'
    verbose_name = 'Autenticación de administrador'
