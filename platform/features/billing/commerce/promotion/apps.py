from django.apps import AppConfig


class PromotionAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.commerce.promotion'
    label = 'promotion'
    verbose_name = 'Promociones'
