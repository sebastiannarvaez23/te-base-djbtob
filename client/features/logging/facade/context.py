"""
logging/facade/context.py
─────────────────────────
Value object que encapsula la metadata común de cualquier log.

Uso desde una view:
    context = LogContextBuilder.from_request(request)

Uso desde un proceso del sistema (cron, command, etc.):
    context = LogContextBuilder.from_system(correlation_id='batch-001')
"""

import uuid
from datetime import datetime
from typing import Optional

from django.utils.timezone import now
from pydantic import BaseModel, Field

from core.auth.integration.principal import IntegrationPrincipal
from core.ids import uuid7


def _as_uuid(value) -> Optional[uuid.UUID]:
    """Acepta un UUID ya tipado o su forma canónica. Un entero legado no es un id."""
    if value is None or value == '':
        return None
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, int):
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


class LogContext(BaseModel):
    """Metadata transversal que acompaña a todo registro de log."""
    user_id: Optional[uuid.UUID] = None
    warehouse_id: Optional[uuid.UUID] = None
    company_subscription_id: Optional[uuid.UUID] = None
    request_id: str = Field(default_factory=lambda: str(uuid7()))
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=now)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class LogContextBuilder:
    """Factory para construir LogContext desde distintas fuentes."""

    @staticmethod
    def from_request(request) -> LogContext:
        user = getattr(request, 'user', None)
        tenant = getattr(request, 'tenant', None)

        request_id = getattr(request, 'request_id', None) or str(uuid7())
        acq_id = getattr(request, 'company_subscription_id', None)
        period_id = None
        if acq_id:
            try:
                period_id = acq_id if isinstance(acq_id, uuid.UUID) else uuid.UUID(str(acq_id))
            except (TypeError, ValueError):
                period_id = None
        is_person = bool(user and user.is_authenticated) and not isinstance(user, IntegrationPrincipal)
        return LogContext(
            user_id=_as_uuid(user.pk) if is_person else None,
            warehouse_id=_as_uuid(getattr(tenant, 'id', None)),
            company_subscription_id=period_id,
            request_id=request_id,
            ip_address=LogContextBuilder._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )

    @staticmethod
    def from_system(correlation_id: str = None) -> LogContext:
        return LogContext(
            correlation_id=correlation_id or str(uuid7()),
        )

    @staticmethod
    def _get_client_ip(request) -> str:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
