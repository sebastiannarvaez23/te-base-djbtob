"""
Punto de integración del sistema de incidencias con el ciclo de request.

El ``RequestLoggingMiddleware`` llama aquí para (1) saber si debe capturar y
resolver la sesión, y (2) empujar la transacción al anillo. Toda la lógica
específica de incidencias vive de este lado; el middleware permanece agnóstico.
"""

import logging
import threading
from datetime import datetime, timezone

import jwt as pyjwt
from django.conf import settings

from core.auth.cookies import ACCESS_ADMIN_COOKIE, ACCESS_CLIENT_COOKIE
from core.logging_redaction import LOGGABLE_CONTENT_TYPES, inline_json
from platform.features.support.incidents.incident.application.capture_transaction import (
    CaptureTransactionUseCase,
)
from platform.features.support.incidents.incident.application.create_draft import (
    CreateIncidentDraftUseCase,
)
from platform.features.support.incidents.incident.infrastructure.redis_buffer import (
    RedisSessionLogBuffer,
)
from platform.features.support.incidents.incident.infrastructure.redis_draft_store import (
    RedisIncidentDraftStore,
)

logger = logging.getLogger('app.api')


def has_client_session(request) -> bool:
    """Chequeo barato al inicio del request: ¿hay cookie de sesión de cliente?

    Evita arrancar la captura para anónimos sin decodificar el token.
    """
    return ACCESS_CLIENT_COOKIE in request.COOKIES


def has_incident_session(request) -> bool:
    """Cookie de cliente o de admin: ambos pueden etiquetar incidencias."""
    cookies = getattr(request, 'COOKIES', {}) or {}
    return ACCESS_CLIENT_COOKIE in cookies or ACCESS_ADMIN_COOKIE in cookies


def resolve_client_session_id(request):
    """Extrae el ``sid`` de la cookie del access token de cliente.

    Decodifica sin verificar expiración (para seguir capturando aunque el token
    esté por rotar) pero validando la firma. Devuelve ``None`` si no aplica.
    """
    return _resolve_session_id(
        request, cookie=ACCESS_CLIENT_COOKIE, user_type='client',
    )


def resolve_admin_session_id(request):
    """Extrae el ``sid`` de la cookie del access token de admin."""
    return _resolve_session_id(
        request, cookie=ACCESS_ADMIN_COOKIE, user_type='admin',
    )


def resolve_incident_session_id(request):
    """Sesión capturable: cliente primero, admin si no hay sid de cliente."""
    return resolve_client_session_id(request) or resolve_admin_session_id(request)


def _resolve_session_id(request, *, cookie: str, user_type: str):
    token = request.COOKIES.get(cookie)
    if not token:
        return None
    try:
        payload = pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=['HS256'],
            options={'verify_exp': False},
        )
    except pyjwt.InvalidTokenError:
        return None
    if payload.get('user_type') != user_type:
        return None
    return payload.get('sid')


def _run_capture(session_id: str, **fields) -> None:
    try:
        CaptureTransactionUseCase(RedisSessionLogBuffer()).execute(session_id, **fields)
    except Exception as exc:
        logger.warning('INCIDENT_CAPTURE_FAILED error=%s', exc)


def capture_transaction(session_id: str, **fields) -> None:
    """Empuja una transacción al anillo de la sesión (best-effort).

    Con ``INCIDENT_CAPTURE_ASYNC`` activo, el push va a un hilo daemon para no
    sumar el RTT de Redis a la latencia del request. Los ``fields`` (incluidos
    los logs ya drenados) son valores planos, así que el hilo no depende de
    contextvars ni del request.
    """
    if getattr(settings, 'INCIDENT_CAPTURE_ASYNC', False):
        threading.Thread(
            target=_run_capture, args=(session_id,), kwargs=fields, daemon=True,
        ).start()
    else:
        _run_capture(session_id, **fields)


def _safe_origin(request) -> str:
    """Origen lógico (app, admin…) del Host; nunca lanza (Host inválido → '')."""
    try:
        return request.get_host().split(':')[0].split('.')[0]
    except Exception:
        return ''


def _read_request_body(request) -> str:
    """Body de envío compactado y enmascarado (mismo criterio que el middleware)."""
    content_type = (getattr(request, 'content_type', '') or '').lower()
    if not content_type.startswith(LOGGABLE_CONTENT_TYPES):
        return f'<{content_type or "sin-body"}>'
    try:
        raw = request.body.decode(getattr(request, 'encoding', None) or 'utf-8', errors='replace')
    except Exception:
        return '<no-legible>'
    return inline_json(raw)


def build_incident_for_error(request, *, error: dict):
    """Congela el draft de una incidencia para un error ≥500 y devuelve el bloque
    ``{token, report_url}`` para el envelope; ``None`` si no aplica.

    No aplica cuando la captura está desactivada o no hay sesión de
    cliente/admin. Best-effort: cualquier fallo devuelve ``None`` sin propagar.
    """
    try:
        if not getattr(settings, 'INCIDENT_CAPTURE_ENABLED', False):
            return None
        session_id = resolve_incident_session_id(request)
        if not session_id:
            return None

        from core.trace import peek_txn_logs
        from core.ui_context import ui_context_dict

        failed_request = {
            'request_id': getattr(request, 'request_id', '-'),
            'ts': datetime.now(timezone.utc).isoformat(),
            'origin': _safe_origin(request),
            'method': getattr(request, 'method', ''),
            'path': getattr(request, 'path', ''),
            'query': request.META.get('QUERY_STRING', '') or '-',
            'request_body': _read_request_body(request),
            'error': error,
            'logs': peek_txn_logs(),
            **ui_context_dict(),
        }
        token = CreateIncidentDraftUseCase(
            RedisSessionLogBuffer(), RedisIncidentDraftStore(),
        ).execute(
            session_id,
            failed_request=failed_request,
            error=error,
            frontend_logs=_frontend_logs_for_draft(request, failed_request, error),
        )
        if not token:
            return None
        return {
            'token': token,
            'report_url': getattr(settings, 'INCIDENT_REPORT_URL', '/api/v1/incidents/report/'),
        }
    except Exception as exc:
        logger.warning('INCIDENT_DRAFT_BUILD_FAILED error=%s', exc)
        return None


def _frontend_logs_for_draft(request, failed_request: dict, error: dict) -> list[dict]:
    """Logs del navegador (header) + línea sintética del 500 que acaba de ocurrir."""
    from platform.features.support.incidents.incident.application.frontend_logs import (
        merge_frontend_logs,
        frontend_logs_from_request,
    )

    method = str(failed_request.get('method') or getattr(request, 'method', '') or 'HTTP')
    path = str(failed_request.get('path') or getattr(request, 'path', '') or '')
    code = str((error or {}).get('code') or 'SRV_001')
    synthetic = [{
        'ts': str(failed_request.get('ts') or ''),
        'level': 'error',
        'message': f'{method} {path} → 500 {code}'.strip(),
    }]
    return merge_frontend_logs(frontend_logs_from_request(request), synthetic)


def report_automated_task_failure(
    *,
    task_id: str,
    task_name: str,
    exc: BaseException,
    traceback_text: str = '',
    task_logs: list[str] | None = None,
    schema_name: str = '',
):
    """Materializa una incidencia por fallo de tarea Celery (best-effort).

    Solo incluye ``task_logs`` (logger ``app.tasks``); no toca el anillo HTTP.
    """
    try:
        if not getattr(settings, 'INCIDENT_TASK_FAILURE_ENABLED', True):
            return None
        if not getattr(settings, 'INCIDENT_CAPTURE_ENABLED', False):
            return None
        from platform.features.support.incidents.incident.application.factory import (
            build_report_task_failure_use_case,
        )
        return build_report_task_failure_use_case().execute(
            task_id=task_id,
            task_name=task_name,
            exc=exc,
            traceback_text=traceback_text,
            task_logs=task_logs,
            schema_name=schema_name,
        )
    except Exception as report_exc:
        logger.warning('INCIDENT_TASK_FAILURE_REPORT_FAILED error=%s', report_exc)
        return None
