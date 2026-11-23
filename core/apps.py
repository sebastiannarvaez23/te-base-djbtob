from django.apps import AppConfig

_sinks_registered = False


def ensure_wa_error_sinks() -> None:
    """Idempotent registration of base incident/security/error sinks into necore."""
    global _sinks_registered
    if _sinks_registered:
        return
    from core.errors.codes import AppErrorCode, ERROR_REGISTRY
    from necore.errors.hooks import (
        register_incident_sink,
        register_security_log_sink,
        register_server_error_sink,
    )
    from necore.errors.registry import configure_error_registry

    configure_error_registry(AppErrorCode, ERROR_REGISTRY)
    register_security_log_sink(_wa_security_log_sink)
    register_server_error_sink(_wa_server_error_sink)
    register_incident_sink(_wa_incident_sink)
    _sinks_registered = True


class CoreConfig(AppConfig):
    name = 'core'
    label = 'core'
    verbose_name = 'Core'

    def ready(self):
        ensure_wa_error_sinks()
        # Also wire flag factory at ready() so necore.is_enabled works even if
        # nothing imported core.flags yet during startup.
        from core.flags.config import get_flag_store
        from necore.flags import set_flag_store_factory

        set_flag_store_factory(get_flag_store)


def _wa_security_log_sink(request, *, event_type, detail=None, trace_id=None):
    try:
        from core.audit import security_log
        security_log(request, event_type=event_type, detail=detail)
    except Exception:
        pass


def _wa_server_error_sink(request, exc, trace_id, *, error_code=None, stacktrace=None):
    try:
        import traceback as _tb
        from client.features.logging.facade.context import LogContextBuilder
        from client.features.logging.facade.factory import LogManagerFactory
        from client.features.logging.system.errors.domain.schemas import ErrorLogSchema
        from necore.errors import ServerException

        ctx = LogContextBuilder.from_request(request) if request else LogContextBuilder.from_system()
        ctx.correlation_id = trace_id
        level = 'CRITICAL' if isinstance(exc, ServerException) else 'ERROR'
        LogManagerFactory.create().error(ctx, ErrorLogSchema(
            level=level,
            error_code=error_code,
            exception_type=type(exc).__name__,
            message=str(exc),
            stacktrace=stacktrace or _tb.format_exc(),
            module=type(exc).__module__,
        ))
    except Exception:
        pass


def _wa_incident_sink(request, *, exc, error_code, http_status, method, path, stacktrace=None):
    if request is None or http_status < 500:
        return None
    try:
        from core.ui_context import ui_context_dict
        from platform.features.support.incidents.incident.integration import (
            build_incident_for_error,
        )

        error = {
            'code': error_code,
            'exception_type': type(exc).__name__,
            'message': str(exc),
            'stacktrace': stacktrace or '',
            'module': type(exc).__module__,
            'http_status': http_status,
            'method': method,
            'path': path,
            'ui_context': ui_context_dict(),
        }
        return build_incident_for_error(request, error=error)
    except Exception:
        return None
