from django.apps import AppConfig


class HandbookIngestAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'handbook.features.docs.governance.ingest'
    label = 'handbook_ingest'
    verbose_name = 'Handbook ingest'
