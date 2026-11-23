"""
CaptureTransactionUseCase — arma una entrada de transacción y la empuja al
anillo por sesión.

No conoce Django ni Redis: recibe valores planos y delega en el puerto
``ISessionLogBuffer``. Testeable con un buffer en memoria.
"""

from typing import Optional

from platform.features.support.incidents.incident.domain.interfaces import ISessionLogBuffer
from platform.features.support.incidents.incident.domain.schemas import TransactionLogEntry


class CaptureTransactionUseCase:
    """Best-effort ring push; intentionally not @trace_layer (noise after every request)."""

    def __init__(self, buffer: ISessionLogBuffer):
        self._buffer = buffer

    def execute(
        self,
        session_id: str,
        *,
        request_id: str,
        ts: str,
        origin: str = '',
        method: str = '',
        path: str = '',
        query: Optional[str] = None,
        request_body: str = '-',
        status: Optional[int] = None,
        response_body: str = '-',
        duration_ms: Optional[float] = None,
        logs: Optional[list] = None,
        module_id: str = '',
        module_code: str = '',
        functionality_id: str = '',
        page_section: str = '',
        feature_key: str = '',
    ) -> None:
        if not session_id:
            return
        entry = TransactionLogEntry(
            request_id=request_id,
            ts=ts,
            origin=origin,
            module_id=module_id,
            module_code=module_code,
            functionality_id=functionality_id,
            page_section=page_section,
            feature_key=feature_key,
            method=method,
            path=path,
            query=query,
            request_body=request_body,
            status=status,
            response_body=response_body,
            duration_ms=duration_ms,
            logs=logs or [],
        )
        self._buffer.append_transaction(session_id, entry)
