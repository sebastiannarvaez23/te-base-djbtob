from django.apps import AppConfig


class SubscriptionFunctionalityAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.subscription.subscription_functionality'
    label = 'subscription_functionality'
    verbose_name = 'Funcionalidades de suscripción'
