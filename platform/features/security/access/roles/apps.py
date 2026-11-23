from django.apps import AppConfig


class PlatformRolesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.security.access.roles'
    label = 'platform_roles'
    verbose_name = 'Roles de administrador'
