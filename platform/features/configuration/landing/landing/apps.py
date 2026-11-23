from django.apps import AppConfig


class LandingAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.configuration.landing.landing'
    label = 'landing'
    verbose_name = 'Landing sections'
