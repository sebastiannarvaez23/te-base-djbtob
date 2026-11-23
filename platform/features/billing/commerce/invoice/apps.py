from django.apps import AppConfig


class InvoiceAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.commerce.invoice'
    label = 'invoice'
    verbose_name = "Factura"

    def ready(self) -> None:
        from platform.features.billing.subscription.subscription.domain.events import PeriodIssued, subscribe
        from .integration.period_issued import PeriodIssuedInvoiceListener
        subscribe(PeriodIssued, PeriodIssuedInvoiceListener().on_period_issued)
