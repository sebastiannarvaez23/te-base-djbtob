from django.apps import AppConfig


class InboxAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.communication.messaging.inbox'
    label = 'inbox'
    verbose_name = 'Notifications — tenant inbox (bell)'
