from django.apps import AppConfig


class RefundAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.commerce.refund'
    label = 'refund'
    verbose_name = 'Reembolso'
