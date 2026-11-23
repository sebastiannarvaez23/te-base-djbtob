"""
core/access/reconcile.py
────────────────────────
Reconciliación genérica de cupos activos tras cambio de plan / período.

Invocado por PeriodIssuedQuotaListener (billing/quota_enforcement). Solo
procesa topes ``lifetime`` cuya feature_key tiene adaptador en
``enforcement_registry``. Sin adaptador → ese tope no se reconcilia aquí
(solo gate en create/activate cuando se cablee el dominio).

Documentación: platform/features/billing/quota_enforcement/EXTENDING.md
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from django.db import transaction

from .enforcement import enforcement_registry

logger = logging.getLogger('app.api')


@dataclass
class FeatureReconcileResult:
    feature_key: str
    max_value: int
    active_before: int
    deactivated_count: int
    deactivated_ids: list[str] = field(default_factory=list)
    incomplete: bool = False


@dataclass
class CompanyQuotaReconcileResult:
    company_id: str
    subscription_id: str
    features: list[FeatureReconcileResult] = field(default_factory=list)


def reconcile_feature_quota(
    company_id: str,
    feature_key: str,
    max_value: int,
) -> FeatureReconcileResult:
    adapter = enforcement_registry.get(feature_key)
    if adapter is None:
        return FeatureReconcileResult(
            feature_key=feature_key,
            max_value=max_value,
            active_before=0,
            deactivated_count=0,
        )

    active_ids = adapter.list_active_entity_ids(company_id)
    active_before = len(active_ids)
    if active_before <= max_value:
        return FeatureReconcileResult(
            feature_key=feature_key,
            max_value=max_value,
            active_before=active_before,
            deactivated_count=0,
        )

    protected = adapter.protected_entity_ids(company_id)
    excess = active_before - max_value
    to_deactivate: list[uuid.UUID] = []

    for entity_id in reversed(active_ids):
        if entity_id in protected:
            continue
        if len(to_deactivate) >= excess:
            break
        to_deactivate.append(entity_id)

    incomplete = len(to_deactivate) < excess
    if incomplete:
        logger.warning(
            'QUOTA_RECONCILE_INCOMPLETE company=%s feature=%s max=%s active=%s '
            'protected=%s could_deactivate=%s',
            company_id, feature_key, max_value, active_before,
            len(protected), len(to_deactivate),
        )

    deactivated_ids: list[str] = []
    with transaction.atomic():
        for entity_id in to_deactivate:
            try:
                adapter.deactivate(entity_id, company_id)
                deactivated_ids.append(str(entity_id))
            except Exception:
                logger.warning(
                    'quota deactivate failed company=%s feature=%s entity=%s',
                    company_id, feature_key, entity_id, exc_info=True,
                )

    return FeatureReconcileResult(
        feature_key=feature_key,
        max_value=max_value,
        active_before=active_before,
        deactivated_count=len(deactivated_ids),
        deactivated_ids=deactivated_ids,
        incomplete=incomplete,
    )


def reconcile_company_quotas(
    company_id: str | uuid.UUID,
    subscription_id: str | uuid.UUID,
    limits: dict,
) -> CompanyQuotaReconcileResult:
    """
    Aplica reconciliación para todos los topes lifetime con adaptador.

    Args:
        company_id: empresa tenant.
        subscription_id: plan activo (metadato de resultado).
        limits: dict {feature_key: {max, type, window_hours?}} del plan activo.
            Debe cargarse en infrastructure (billing); core no importa ORM de platform.
    """
    company_id_str = str(company_id)
    subscription_id_str = str(subscription_id)

    result = CompanyQuotaReconcileResult(
        company_id=company_id_str,
        subscription_id=subscription_id_str,
    )

    for feature_key, config in limits.items():
        if config.get('type') != 'lifetime':
            continue
        if not enforcement_registry.has(feature_key):
            continue
        max_value = int(config['max'])
        feature_result = reconcile_feature_quota(company_id_str, feature_key, max_value)
        if feature_result.deactivated_count or feature_result.incomplete:
            result.features.append(feature_result)
            logger.info(
                'QUOTA_RECONCILED company=%s feature=%s max=%s before=%s deactivated=%s',
                company_id_str,
                feature_key,
                max_value,
                feature_result.active_before,
                feature_result.deactivated_count,
            )

    return result
