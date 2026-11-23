from django.apps import AppConfig


class ModelRoutingAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.configuration.ai.model_routing'
    label = 'ai_model_routing'
    verbose_name = 'AI model routing'
