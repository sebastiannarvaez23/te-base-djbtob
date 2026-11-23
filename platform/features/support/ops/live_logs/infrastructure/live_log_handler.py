"""logging.Handler that fans out structured lines to WS + Redis ring."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from django.conf import settings

from core.ids import uuid7
from core.logging_redaction import redact_log_message
from core.trace import get_session_id, get_tenant, get_trace_id, get_user_id, get_username
from platform.features.support.ops.live_logs.domain.catalog import channel_for_logger
from platform.features.support.ops.live_logs.domain.schemas import LiveLogLineView
from platform.features.support.ops.live_logs.infrastructure.realtime_publisher import (
    LiveLogsRealtimePublisher,
)
from platform.features.support.ops.live_logs.infrastructure.redis_ring import (
    RedisLiveLogRingBuffer,
)

_tls = threading.local()


class LiveLogStreamHandler(logging.Handler):
    """Best-effort fan-out; never raises into the caller's logging path."""

    def __init__(self, publisher=None, ring=None, level=logging.NOTSET):
        super().__init__(level=level)
        self._publisher = publisher or LiveLogsRealtimePublisher()
        self._ring = ring or RedisLiveLogRingBuffer()
        self._max_chars = int(getattr(settings, 'LIVE_LOGS_MAX_MESSAGE_CHARS', 2000))

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(_tls, 'emitting', False):
            return
        channel = channel_for_logger(record.name)
        if channel is None:
            return

        _tls.emitting = True
        try:
            line = self._to_line(record, channel.key)
        except Exception:
            self.handleError(record)
            return
        finally:
            _tls.emitting = False

        try:
            if bool(getattr(settings, 'LIVE_LOGS_CAPTURE_ASYNC', True)):
                threading.Thread(
                    target=self._fan_out,
                    args=(line,),
                    daemon=True,
                    name='live-logs-fanout',
                ).start()
            else:
                self._fan_out(line)
        except Exception:
            self.handleError(record)

    def _fan_out(self, line: LiveLogLineView) -> None:
        # Worker TLS: suppress re-entry if ring/publisher log to app.* channels.
        _tls.emitting = True
        try:
            try:
                self._ring.append(line)
            except Exception:
                pass
            try:
                self._publisher.emit_line(line)
            except Exception:
                pass
        finally:
            _tls.emitting = False

    def _to_line(self, record: logging.LogRecord, channel_key: str) -> LiveLogLineView:
        message = redact_log_message(record.getMessage())
        if len(message) > self._max_chars:
            message = message[: self._max_chars - 1] + '…'

        trace_id = getattr(record, 'trace_id', None) or '-'
        if trace_id == '-':
            try:
                trace_id = get_trace_id() or '-'
            except Exception:
                trace_id = '-'

        schema_name = None
        try:
            schema_name = get_tenant() or None
        except Exception:
            schema_name = None
        if not schema_name:
            schema_name = getattr(record, 'schema_name', None) or None

        session_id = None
        try:
            session_id = get_session_id() or None
        except Exception:
            session_id = None
        if not session_id:
            raw_sid = getattr(record, 'session_id', None)
            session_id = str(raw_sid) if raw_sid else None

        username = None
        try:
            username = get_username() or None
        except Exception:
            username = None
        if not username:
            raw_user = getattr(record, 'username', None)
            username = str(raw_user) if raw_user else None

        user_id = None
        try:
            user_id = get_user_id() or None
        except Exception:
            user_id = None
        if not user_id:
            raw_uid = getattr(record, 'user_id', None)
            user_id = str(raw_uid) if raw_uid else None

        error_code = getattr(record, 'error_code', None)
        if error_code in (None, '-', ''):
            error_code = None

        ts = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return LiveLogLineView(
            id=str(uuid7()),
            ts=ts,
            channel=channel_key,
            level=record.levelname,
            logger=record.name,
            message=message,
            trace_id=str(trace_id),
            session_id=session_id or None,
            username=username or None,
            user_id=user_id or None,
            schema_name=schema_name or None,
            error_code=error_code,
        )
