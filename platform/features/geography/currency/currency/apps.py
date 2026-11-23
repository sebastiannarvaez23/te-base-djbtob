from django.apps import AppConfig


class GeographyCurrencyAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.geography.currency.currency'
    label = 'geography_currency'
    verbose_name = 'Geography currencies'
