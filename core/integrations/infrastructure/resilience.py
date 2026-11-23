"""Reintentos y circuit breaker ligero por conexión."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, TypeVar

from django.conf import settings

from core.errors import AppErrorCode
from core.errors.exceptions import ServerException
from core.integrations.domain.enums import CircuitState

logger = logging.getLogger('app.integrations')

T = TypeVar('T')

_TRANSIENT_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


@dataclass
class _CircuitRecord:
    failures: int = 0
    state: CircuitState = CircuitState.CLOSED
    opened_at: float = 0.0


_circuits: dict[str, _CircuitRecord] = {}


def _failure_threshold() -> int:
    return int(getattr(settings, 'INTEGRATIONS_CIRCUIT_FAILURE_THRESHOLD', 5))


def _circuit_key(connection_id: str) -> str:
    return str(connection_id)


def assert_circuit_closed(connection_id: str) -> None:
    record = _circuits.get(_circuit_key(connection_id))
    if record and record.state == CircuitState.OPEN:
        raise ServerException(
            AppErrorCode.INT_PROVIDER_UNAVAILABLE,
            override_detail='Integration circuit is open due to repeated failures.',
            context={'connection_id': connection_id},
        )


def record_success(connection_id: str) -> None:
    key = _circuit_key(connection_id)
    if key in _circuits:
        _circuits[key] = _CircuitRecord()


def record_failure(connection_id: str) -> CircuitState:
    key = _circuit_key(connection_id)
    record = _circuits.get(key, _CircuitRecord())
    record.failures += 1
    if record.failures >= _failure_threshold():
        record.state = CircuitState.OPEN
        record.opened_at = time.monotonic()
        logger.warning('integration circuit opened connection=%s failures=%s', connection_id, record.failures)
    _circuits[key] = record
    return record.state


def reset_circuits() -> None:
    """Solo para tests."""
    _circuits.clear()


def is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, _TRANSIENT_EXCEPTIONS):
        return True
    if isinstance(exc, ServerException):
        return exc.code in (
            AppErrorCode.INT_TIMEOUT,
            AppErrorCode.INT_PROVIDER_UNAVAILABLE,
        )
    return False


def with_transient_retries(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    connection_id: str | None = None,
) -> T:
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = fn()
            if connection_id:
                record_success(connection_id)
            return result
        except BaseException as exc:
            last_exc = exc
            if not is_transient_error(exc) or attempt >= max_attempts:
                if connection_id and is_transient_error(exc):
                    record_failure(connection_id)
                raise
            logger.warning(
                'integration transient retry attempt=%s connection=%s error=%s',
                attempt,
                connection_id,
                exc,
            )
    assert last_exc is not None
    raise last_exc
