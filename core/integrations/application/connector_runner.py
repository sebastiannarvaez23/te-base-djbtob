"""ConnectorRunner — ejecuta operaciones con timeout, idempotencia y logging."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable, TypeVar

from django.conf import settings

from core.errors import AppErrorCode
from core.errors.exceptions import ConflictException, ServerException
from core.integrations.config import get_idempotency_store, is_integrations_enabled
from core.integrations.domain.interfaces import IIdempotencyStore
from core.integrations.domain.schemas import ConnectionProfile, OperationContext, SyncRequest
from core.integrations.infrastructure.resilience import assert_circuit_closed, with_transient_retries
from core.integrations.observability import integration_logger, metrics

logger = logging.getLogger('app.integrations')

T = TypeVar('T')


class ConnectorRunner:
    """Orquesta una operación de conector con garantías transversales."""

    def __init__(self, idempotency_store: IIdempotencyStore | None = None):
        self._idempotency = idempotency_store

    def _store(self) -> IIdempotencyStore:
        return self._idempotency or get_idempotency_store()

    def run(
        self,
        operation: Callable[..., T],
        request: SyncRequest | ConnectionProfile,
        *,
        context: OperationContext,
    ) -> T:
        if not is_integrations_enabled():
            raise ServerException(AppErrorCode.INT_DISABLED)

        profile = request.profile if isinstance(request, SyncRequest) else request
        connection_id = str(context.connection_id)
        assert_circuit_closed(connection_id)

        idem_key = context.idempotency_key or self._default_idempotency_key(
            context, profile, request,
        )
        scope = f'{context.tenant_schema}:{connection_id}'
        cached = self._store().get(scope, idem_key)
        if cached is not None:
            metrics.increment('integrations.idempotency_hit')
            raise ConflictException(
                AppErrorCode.INT_DUPLICATE_IDEMPOTENT,
                context={'idempotency_key': idem_key},
            )

        timeout = float(getattr(settings, 'INTEGRATIONS_DEFAULT_TIMEOUT_SECONDS', 30.0))
        started = time.monotonic()

        def _execute() -> T:
            return self._call_with_timeout(operation, request, timeout)

        try:
            result = with_transient_retries(
                _execute,
                connection_id=connection_id,
            )
        except FuturesTimeoutError as exc:
            metrics.increment('integrations.timeout')
            self._log_operation(
                profile, context, request, None, started,
                error=AppErrorCode.INT_TIMEOUT.value,
            )
            raise ServerException(AppErrorCode.INT_TIMEOUT) from exc
        except ServerException:
            metrics.increment('integrations.error')
            self._log_operation(
                profile, context, request, None, started, error='server_error',
            )
            raise
        except Exception as exc:
            metrics.increment('integrations.error')
            self._log_operation(profile, context, request, None, started, error=str(exc))
            raise ServerException(
                AppErrorCode.INT_PROVIDER_UNAVAILABLE,
                override_detail=str(exc),
            ) from exc

        self._store().put(scope, idem_key, {'result_type': type(result).__name__})
        metrics.increment('integrations.success')
        self._log_operation(profile, context, request, result, started)
        return result

    def _call_with_timeout(
        self,
        operation: Callable[..., T],
        request: SyncRequest | ConnectionProfile,
        timeout: float,
    ) -> T:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(operation, request)
            return future.result(timeout=timeout)

    def _default_idempotency_key(
        self,
        context: OperationContext,
        profile: ConnectionProfile,
        request: SyncRequest | ConnectionProfile,
    ) -> str:
        payload = {
            'operation': context.operation,
            'provider': profile.provider.value,
            'connection_id': str(profile.connection_id),
        }
        if isinstance(request, SyncRequest):
            payload.update({
                'entity': request.entity,
                'direction': request.direction.value,
                'dry_run': request.dry_run,
                'cursor': request.cursor,
            })
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    def _log_operation(
        self,
        profile: ConnectionProfile,
        context: OperationContext,
        request: SyncRequest | ConnectionProfile,
        result: Any,
        started: float,
        *,
        error: str | None = None,
    ) -> None:
        duration_ms = int((time.monotonic() - started) * 1000)
        response_body = None
        status_code = 200
        if error:
            status_code = 502
        elif result is not None and hasattr(result, 'model_dump'):
            response_body = result.model_dump()
        elif result is not None:
            response_body = {'value': str(result)}

        request_body: dict[str, Any] = {
            'operation': context.operation,
            'provider': profile.provider.value,
        }
        if isinstance(request, SyncRequest):
            request_body.update({
                'entity': request.entity,
                'direction': request.direction.value,
                'dry_run': request.dry_run,
            })

        integration_logger.log_integration_event(
            system=profile.provider.value,
            direction='outbound',
            endpoint=context.operation,
            method='POST',
            request_body=request_body,
            response_body=response_body,
            status_code=status_code,
            duration_ms=duration_ms,
            error_message=error,
            request_id=context.request_id,
            user_id=context.user_id,
            warehouse_id=context.warehouse_id,
        )
