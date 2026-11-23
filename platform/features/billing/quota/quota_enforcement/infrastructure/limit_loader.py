"""Carga topes de suscripción desde PostgreSQL (capa infrastructure)."""

from __future__ import annotations

import uuid


def load_subscription_limit_map(subscription_id: uuid.UUID | str) -> dict[str, dict]:
    from platform.features.billing.subscription.subscription_limit.models import SubscriptionLimit

    qs = SubscriptionLimit.objects.filter(
        subscription_id=subscription_id,
    ).select_related('functionality')
    return {
        sl.functionality.key: {
            'max': sl.max_value,
            'type': sl.validation_type,
            'window_hours': sl.window_hours,
        }
        for sl in qs
    }
