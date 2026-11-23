from django.apps import AppConfig


class GeographyLocationAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.geography.location.location'
    label = 'geography_location'
    verbose_name = 'Geography locations'
