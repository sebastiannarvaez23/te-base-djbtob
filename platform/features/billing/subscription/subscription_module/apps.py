from django.apps import AppConfig


class SubscriptionModuleAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.subscription.subscription_module'
    label = 'subscription_module'
    verbose_name = 'Módulos de suscripción'
