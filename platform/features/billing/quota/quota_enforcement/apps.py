from django.apps import AppConfig


class QuotaEnforcementAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'platform.features.billing.quota.quota_enforcement'
    label = 'quota_enforcement'
    verbose_name = 'Enforcement de cupos'

    def ready(self) -> None:
        # Listener PeriodIssued → reconciliación de cupos activos.
        # Guía: platform/features/billing/quota_enforcement/EXTENDING.md
        from platform.features.billing.subscription.subscription.domain.events import PeriodIssued, subscribe
        from .integration.period_issued import PeriodIssuedQuotaListener

        subscribe(PeriodIssued, PeriodIssuedQuotaListener().on_period_issued)
