from django.apps import AppConfig


class RegistrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client.features.security.lifecycle.registration'
    label = 'registration'

    def ready(self) -> None:
        # Cupos activos: registra adaptadores en enforcement_registry.
        # Ver platform/features/billing/quota_enforcement/EXTENDING.md
        from .quota_adapters import register_quota_adapters

        register_quota_adapters()
