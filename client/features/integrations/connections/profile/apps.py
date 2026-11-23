from django.apps import AppConfig


class IntegrationsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.integrations.connections.profile'
    label = 'integrations'
    verbose_name = 'Integrations'
