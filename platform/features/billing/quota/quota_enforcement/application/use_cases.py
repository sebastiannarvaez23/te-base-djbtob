"""Reconciliación de cupos activos al emitir un nuevo período de suscripción.

No añadir lógica por dominio aquí. Nuevos recursos → adaptador + EXTENDING.md.
"""
import logging

from core.access.reconcile import reconcile_company_quotas
from platform.features.billing.quota.quota_enforcement.domain.schemas import (
    CompanyQuotaReconcileSchema,
    FeatureQuotaReconcileSchema,
)
from platform.features.billing.quota.quota_enforcement.infrastructure.limit_loader import (
    load_subscription_limit_map,
)
from platform.features.billing.subscription.subscription.domain.events import PeriodIssued
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class ReconcileCompanyQuotasUseCase:
    """
    Inactiva excedentes según topes lifetime del plan activo.

    Entrada típica: PeriodIssued tras activate_plan (upgrade, downgrade,
    renovación). Idempotente si ya no hay excedentes.
    """

    @trace_layer('application')
    def execute(self, company_id, subscription_id) -> CompanyQuotaReconcileSchema:
        limits = load_subscription_limit_map(subscription_id)
        result = reconcile_company_quotas(company_id, subscription_id, limits=limits)
        return CompanyQuotaReconcileSchema(
            company_id=result.company_id,
            subscription_id=result.subscription_id,
            features=[
                FeatureQuotaReconcileSchema(
                    feature_key=f.feature_key,
                    max_value=f.max_value,
                    active_before=f.active_before,
                    deactivated_count=f.deactivated_count,
                    deactivated_ids=f.deactivated_ids,
                    incomplete=f.incomplete,
                )
                for f in result.features
            ],
        )


class PeriodIssuedQuotaListener:
    """Suscrito en quota_enforcement/apps.py al bus PeriodIssued."""

    def on_period_issued(self, event: PeriodIssued) -> None:
        try:
            ReconcileCompanyQuotasUseCase().execute(
                event.company_id,
                event.subscription_id,
            )
        except Exception:
            logger.warning(
                'quota reconcile failed company=%s subscription=%s',
                event.company_id,
                event.subscription_id,
                exc_info=True,
            )
