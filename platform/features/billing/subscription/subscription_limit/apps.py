from django.apps import AppConfig


class SubscriptionLimitAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.subscription.subscription_limit'
    label = 'subscription_limit'
    verbose_name = 'Topes de suscripción'
