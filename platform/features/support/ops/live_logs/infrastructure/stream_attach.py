"""Attach LiveLogStreamHandler to catalog loggers (idempotent).

Wired from ``SupportLiveLogsAppConfig.ready()`` — not Django LOGGING
dictConfig — because configure_logging runs before apps are populated.
"""

from __future__ import annotations

import logging

from django.conf import settings

from platform.features.support.ops.live_logs.domain.catalog import LIVE_LOG_CHANNELS
from platform.features.support.ops.live_logs.infrastructure.live_log_handler import (
    LiveLogStreamHandler,
)

_ATTACHED = False
_HANDLER: LiveLogStreamHandler | None = None


def _installed_handler() -> LiveLogStreamHandler | None:
    """Handler presente en todos los canales. ``dictConfig`` puede quitarlo."""
    found: LiveLogStreamHandler | None = None
    for channel in LIVE_LOG_CHANNELS:
        lg = logging.getLogger(channel.logger_name)
        match = next((h for h in lg.handlers if isinstance(h, LiveLogStreamHandler)), None)
        if match is None:
            return None
        found = match
    return found


def attach_live_log_handlers() -> LiveLogStreamHandler | None:
    """Idempotent attach. Reinstala el handler si un ``dictConfig`` posterior lo quitó.

    ``runserver`` llama ``django.setup()`` dos veces: ``ready()`` engancha el
    handler y el ``get_wsgi_application()`` siguiente reconfigura el logging
    y lo elimina. Hay que volver a engancharlo después de ese segundo setup.
    """
    global _ATTACHED, _HANDLER
    if not getattr(settings, 'LIVE_LOGS_ENABLED', True):
        return None

    installed = _installed_handler()
    if installed is not None:
        _HANDLER = installed
        _ATTACHED = True
        return installed

    if _HANDLER is None:
        min_level_name = str(getattr(settings, 'LIVE_LOGS_MIN_LEVEL', 'INFO')).upper()
        min_level = getattr(logging, min_level_name, logging.INFO)
        _HANDLER = LiveLogStreamHandler(level=min_level)

    for channel in LIVE_LOG_CHANNELS:
        lg = logging.getLogger(channel.logger_name)
        if any(h is _HANDLER for h in lg.handlers):
            continue
        lg.addHandler(_HANDLER)

    _ATTACHED = True
    return _HANDLER


def reset_live_log_attach_state() -> None:
    """Test helper: clear module attach flags."""
    global _ATTACHED, _HANDLER
    _ATTACHED = False
    _HANDLER = None
