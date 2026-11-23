from django.apps import AppConfig


class EmailTemplateAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.communication.email.email_template'
    label = 'email_template'
    verbose_name = 'Email templates'
