"""Facade de logging hacia client/features/logging/integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

from core.logging_redaction import mask_secrets

logger = logging.getLogger('app.integrations')


def log_integration_event(
    *,
    system: str,
    direction: str,
    endpoint: str,
    method: str,
    request_body: Optional[dict[str, Any]] = None,
    response_body: Optional[dict[str, Any]] = None,
    status_code: Optional[int] = None,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    request_id: str = '-',
    user_id: Optional[int] = None,
    warehouse_id: Optional[int] = None,
) -> None:
    """
    Persiste un evento de integración (best-effort).

    Delega en ``LogManagerFactory`` del tenant cuando está disponible;
    nunca interrumpe el flujo principal.
    """
    try:
        from client.features.logging.facade.context import LogContextBuilder
        from client.features.logging.facade.factory import LogManagerFactory
        from client.features.logging.ops.integration.domain.schemas import IntegrationLogInputSchema

        context = LogContextBuilder.from_system('integrations')
        if user_id is not None:
            context.user_id = user_id
        if warehouse_id is not None:
            context.warehouse_id = warehouse_id
        context.request_id = request_id

        data = IntegrationLogInputSchema(
            system=system,
            direction=direction,
            endpoint=endpoint,
            method=method,
            request_body=mask_secrets(request_body) if request_body else None,
            response_body=mask_secrets(response_body) if response_body else None,
            status_code=status_code,
            duration_ms=duration_ms,
            error_message=error_message,
        )
        LogManagerFactory.create().integration(context, data)
    except Exception as exc:
        logger.warning('integration log failed (best-effort): %s', exc)
