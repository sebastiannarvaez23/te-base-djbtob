from django.apps import AppConfig


class AssistantCredentialsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.communication.assistant.credentials'
    label = 'assistant_credentials'
    verbose_name = 'assistant BYOK credentials'
