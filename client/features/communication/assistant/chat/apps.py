from django.apps import AppConfig


class AssistantAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.communication.assistant.chat'
    label = 'assistant'
    verbose_name = 'assistant (copiloto)'
