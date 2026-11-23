from django.apps import AppConfig


class ModuleFiltersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.security.identity.module_filters'
    label = 'module_filters'
    verbose_name = 'Filtros avanzados por usuario'
