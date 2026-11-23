from django.apps import AppConfig


class ConnectorCatalogAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.integrations.connector_catalog.connector_catalog'
    label = 'integrations_catalog'
    verbose_name = 'Integration connector catalog'
