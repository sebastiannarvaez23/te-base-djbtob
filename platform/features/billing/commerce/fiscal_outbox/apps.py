from django.apps import AppConfig


class FiscalOutboxAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.commerce.fiscal_outbox'
    label = 'fiscal_outbox'
    verbose_name = 'Fiscal outbox'
