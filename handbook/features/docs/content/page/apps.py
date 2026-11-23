from django.apps import AppConfig


class HandbookPageAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'handbook.features.docs.content.page'
    label = 'handbook_page'
    verbose_name = 'Handbook pages'
