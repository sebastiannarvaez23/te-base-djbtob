"""Período de suscripción que todavía da acceso a la empresa.

Una cancelación conserva el acceso hasta ``end_date``. No es una suspensión
de la empresa.
"""
from __future__ import annotations

from datetime import datetime

from django.db.models import Q
from django.utils import timezone


def entitled_acquisition_q(now: datetime | None = None) -> Q:
    """Activa, o cancelada con la vigencia todavía abierta."""
    from platform.features.billing.subscription.subscription.models import CompanySubscription

    moment = now or timezone.now()
    return Q(status=CompanySubscription.Status.ACTIVE) | Q(
        status=CompanySubscription.Status.CANCELLED,
        end_date__gt=moment,
    )


def acquisition_grants_access(acquisition, now: datetime | None = None) -> bool:
    """True si esa fila de suscripción permite entrar y operar."""
    if acquisition is None:
        return False
    from platform.features.billing.subscription.subscription.models import CompanySubscription

    status = getattr(acquisition, 'status', None)
    if status == CompanySubscription.Status.ACTIVE:
        return True
    if status != CompanySubscription.Status.CANCELLED:
        return False
    end = getattr(acquisition, 'end_date', None)
    if not isinstance(end, datetime):
        return False
    moment = now or timezone.now()
    if timezone.is_naive(end) and timezone.is_aware(moment):
        end = timezone.make_aware(end, timezone.get_current_timezone())
    return end > moment
