from django.apps import AppConfig


class PlatformUsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.security.identity.users'
    label = 'platform_users'
    verbose_name = 'Usuarios de administrador'
