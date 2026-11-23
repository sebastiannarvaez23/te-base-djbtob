from django.apps import AppConfig


class EmailSenderConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.communication.email.email_sender'
    label = 'email_sender'
