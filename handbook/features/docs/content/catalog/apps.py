from django.apps import AppConfig


class HandbookCatalogAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'handbook.features.docs.content.catalog'
    label = 'handbook_catalog'
    verbose_name = 'Handbook catalog'
