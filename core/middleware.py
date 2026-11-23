"""
core/middleware.py
------------------
Middleware transversal de la aplicacion.
"""

import logging
import time
from datetime import datetime, timezone

from django.conf import settings

from core.ids import uuid7

from core.auth.cookies import ACCESS_ADMIN_COOKIE, ACCESS_CLIENT_COOKIE
from core.logging_redaction import LOGGABLE_CONTENT_TYPES, inline_json

request_logger = logging.getLogger('app.request')


class RequestIDMiddleware:
    """Genera un request_id unico (uuid7) para cada peticion.

    Siempre se genera en servidor: un ``X-Request-ID`` del cliente no se
    reutiliza como clave primaria (colisión bajo concurrencia rompería el
    buffer de consola ordenada y la correlación de logs). Si el cliente envía
    el header, se guarda en ``request.client_request_id`` para correlación
    externa sin usarlo como id interno.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        client_id = (request.META.get('HTTP_X_REQUEST_ID') or '').strip() or None
        request_id = str(uuid7())
        request.client_request_id = client_id
        request.request_id = request_id
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        if client_id:
            response['X-Client-Request-ID'] = client_id[:128]
        return response


def _resolve_origin(request):
    """Deriva el origen logico (app, admin, …) del Host de la peticion."""
    host = request.get_host().split(':')[0]
    label = host.split('.')[0]
    return label or host


class RequestLoggingMiddleware:
    """Loguea cada request/response en la terminal con trazabilidad completa.

    Emite una linea al entrar (``>> REQ``) y otra al salir (``<< RES``) al
    logger ``app.request``, incluyendo request_id, origen, metodo, endpoint,
    query params, body JSON en linea y la respuesta (o excepcion) tambien en
    linea. Debe declararse DESPUES de ``RequestIDMiddleware`` para reutilizar
    ``request.request_id``.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._skip_paths = tuple(getattr(settings, 'REQUEST_LOG_SKIP_PATHS', ()))
        self._log_bodies = getattr(settings, 'REQUEST_LOG_BODIES', False)
        self._incident_enabled = getattr(settings, 'INCIDENT_CAPTURE_ENABLED', False)

    def __call__(self, request):
        if any(request.path.startswith(p) for p in self._skip_paths):
            return self.get_response(request)

        request_id = getattr(request, 'request_id', '-')
        tenant = getattr(request, 'tenant', None)
        schema = getattr(tenant, 'schema_name', '') or ''
        from core.trace import (
            bind_actor_from_request,
            drain_txn_logs,
            set_session_id,
            set_tenant,
            set_trace_id,
            set_user_id,
            set_username,
            start_txn_capture,
        )
        from core.ui_context import reset_ui_context, set_ui_context, ui_context_from_request
        from core.logging_handlers import OrderedRequestConsoleHandler

        set_trace_id(request_id)
        set_tenant(schema)
        OrderedRequestConsoleHandler.open_request(request_id)

        try:
            from platform.features.support.incidents.incident.integration import (
                resolve_incident_session_id,
            )
            set_session_id(resolve_incident_session_id(request) or '')
        except Exception:
            set_session_id('')

        # Actor (username) desde JWT/cookies — disponible ya en REQ y procedimiento.
        bind_actor_from_request(request)

        capturing = self._incident_enabled and (
            ACCESS_CLIENT_COOKIE in request.COOKIES
            or ACCESS_ADMIN_COOKIE in request.COOKIES
        )
        if capturing:
            start_txn_capture()
            set_ui_context(ui_context_from_request(request))

        origin = _resolve_origin(request)
        query = request.META.get('QUERY_STRING', '') or '-'
        extra = {'trace_id': request_id}
        # El body de envío se lee una sola vez si se necesita (log y/o captura).
        req_body = self._read_body(request) if (self._log_bodies or capturing) else None
        ts = datetime.now(timezone.utc).isoformat()

        try:
            if self._log_bodies:
                request_logger.info(
                    '>> REQ origin=%s method=%s path=%s query=%s body=%s',
                    origin, request.method, request.path, query, req_body, extra=extra,
                )
            else:
                request_logger.info(
                    '>> REQ origin=%s method=%s path=%s query=%s',
                    origin, request.method, request.path, query, extra=extra,
                )

            started = time.monotonic()
            response = self.get_response(request)
            elapsed_ms = (time.monotonic() - started) * 1000

            # Auth corre dentro de get_response; enlaza actor antes del RES.
            bind_actor_from_request(request)

            res_body = self._read_response(response) if (self._log_bodies or capturing) else None
            if self._log_bodies:
                request_logger.info(
                    '<< RES origin=%s method=%s path=%s status=%s time=%.1fms body=%s',
                    origin, request.method, request.path, response.status_code,
                    elapsed_ms, res_body, extra=extra,
                )
            else:
                request_logger.info(
                    '<< RES origin=%s method=%s path=%s status=%s time=%.1fms',
                    origin, request.method, request.path, response.status_code,
                    elapsed_ms, extra=extra,
                )

            if capturing:
                self._capture(request, request_id, ts, origin, query, req_body,
                              response.status_code, res_body, elapsed_ms)
            return response
        finally:
            # Vuelca REQ + proceso + RES como un solo bloque (sin intercalado).
            OrderedRequestConsoleHandler.flush_request(request_id)
            # Cierra la captura (reset) y evita que trace/tenant se filtren
            # al siguiente request del hilo.
            if capturing:
                drain_txn_logs()
            reset_ui_context()
            set_tenant('')
            set_session_id('')
            set_username('')
            set_user_id('')
            set_trace_id('-')

    def _capture(self, request, request_id, ts, origin, query, req_body,
                 status, res_body, elapsed_ms):
        """Empuja la transacción al anillo de la sesión (best-effort, silencioso)."""
        try:
            from core.trace import drain_txn_logs
            from core.ui_context import ui_context_dict
            from platform.features.support.incidents.incident import integration as incident

            session_id = incident.resolve_incident_session_id(request)
            if not session_id:
                return
            incident.capture_transaction(
                session_id,
                request_id=request_id, ts=ts, origin=origin,
                method=request.method, path=request.path, query=query,
                request_body=req_body or '-', status=status,
                response_body=res_body or '-', duration_ms=round(elapsed_ms, 1),
                logs=drain_txn_logs(),
                **ui_context_dict(),
            )
        except Exception:
            # Nunca romper el request por un fallo de captura.
            pass

    def process_exception(self, request, exception):
        """Loguea excepciones no capturadas en linea (el flujo sigue su curso)."""
        request_logger.error(
            '!! EXC path=%s exc=%s detail=%s',
            request.path, type(exception).__name__, str(exception),
            extra={'trace_id': getattr(request, 'request_id', '-')},
        )
        return None

    @staticmethod
    def _read_body(request):
        content_type = (request.content_type or '').lower()
        if not content_type.startswith(LOGGABLE_CONTENT_TYPES):
            return f'<{content_type or "sin-body"}>'
        try:
            raw = request.body.decode(request.encoding or 'utf-8', errors='replace')
        except Exception:
            return '<no-legible>'
        return inline_json(raw)

    @staticmethod
    def _read_response(response):
        if getattr(response, 'streaming', False):
            return '<streaming>'
        content_type = response.get('Content-Type', '').lower()
        if not content_type.startswith(LOGGABLE_CONTENT_TYPES):
            return f'<{content_type or "sin-body"}>'
        try:
            raw = response.content.decode('utf-8', errors='replace')
        except Exception:
            return '<no-legible>'
        return inline_json(raw)


class ObservabilityActorMiddleware:
    """Publica username/user_id en ContextVar tras la autenticación.

    Debe ir DESPUÉS de ``AuthenticationMiddleware`` para que los logs de
    procedimiento (durante la vista) ya lleven el actor. No limpia el
    contexto: eso lo hace ``RequestLoggingMiddleware`` al cerrar el request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from core.trace import bind_actor_from_request
        bind_actor_from_request(request)
        return self.get_response(request)
