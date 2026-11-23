from django.apps import AppConfig


class InboxPlatformAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.communication.messaging.inbox'
    label = 'inbox_platform'
    verbose_name = 'Notifications — platform (public)'
