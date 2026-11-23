from django.apps import AppConfig


class HandbookChangeRequestAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'handbook.features.docs.governance.change_request'
    label = 'handbook_change_request'
    verbose_name = 'Handbook change requests'
