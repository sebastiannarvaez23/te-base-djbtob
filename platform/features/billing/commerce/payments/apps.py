from django.apps import AppConfig


class PaymentsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.commerce.payments'
    label = 'payments'
    verbose_name = "Pagos"

    def ready(self) -> None:
        """
        Suscribe los listeners del módulo al bus de eventos.

        Se ejecuta una sola vez cuando Django carga la app. El bus es
        un singleton de módulo; ``subscribe`` es idempotente, así que
        reloads de autoreload en dev no duplican handlers.
        """
        from .domain.events import (
            PaymentCanceled,
            PaymentCaptured,
            PaymentFailed,
            PaymentRefunded,
            subscribe,
        )
        from .integration.events import InvoiceIssued
        from .integration.invoice_billing import InvoiceBillingListener
        from .integration.invoice_delivery import InvoiceDeliveryListener

        listener = InvoiceBillingListener()
        subscribe(PaymentCaptured, listener.on_payment_captured)
        subscribe(PaymentFailed,   listener.on_payment_failed)
        subscribe(PaymentCanceled, listener.on_payment_canceled)
        subscribe(PaymentRefunded, listener.on_payment_refunded)

        from platform.features.billing.subscription.subscription.domain.events import (
            PeriodIssued,
            subscribe as subscribe_period,
        )
        from .integration.period_issued import PeriodIssuedChargeListener
        subscribe_period(PeriodIssued, PeriodIssuedChargeListener().on_period_issued)

        # Delivery reacts to InvoiceIssued (published by the billing listener
        # once the invoice exists), NOT to PaymentCaptured — so it no longer
        # depends on handler ordering or event mutation.
        delivery = InvoiceDeliveryListener()
        subscribe(InvoiceIssued, delivery.on_invoice_issued)

        from .integration.fiscal_invoicing import (
            FiscalInvoicingListener,
            FiscalVoidOnRefundListener,
        )
        subscribe(InvoiceIssued, FiscalInvoicingListener().on_invoice_issued)
        subscribe(PaymentRefunded, FiscalVoidOnRefundListener().on_payment_refunded)
