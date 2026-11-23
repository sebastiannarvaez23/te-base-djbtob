from django.apps import AppConfig


class PaymentMethodAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.commerce.payment_method'
    label = 'payment_method'
    verbose_name = "Método de Pago"
