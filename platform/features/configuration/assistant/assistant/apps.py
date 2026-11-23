from django.apps import AppConfig


class AssistantSettingsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.configuration.assistant.assistant'
    label = 'assistant_settings'
    verbose_name = 'assistant settings'
