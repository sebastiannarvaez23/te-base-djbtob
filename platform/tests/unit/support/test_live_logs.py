"""Unit tests for live-logs catalog, ring buffer, handler and use cases."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.test import override_settings

from platform.features.support.ops.live_logs.application.use_cases import (
    GetRecentLiveLogsUseCase,
    ListLiveLogChannelsUseCase,
)
from platform.features.support.ops.live_logs.domain.catalog import (
    LEVEL_CHOICES,
    LIVE_LOG_CHANNELS,
    channel_for_logger,
)
from platform.features.support.ops.live_logs.domain.schemas import LiveLogLineView
from platform.features.support.ops.live_logs.infrastructure import redis_ring
from platform.features.support.ops.live_logs.infrastructure.live_log_handler import (
    LiveLogStreamHandler,
)
from platform.features.support.ops.live_logs.infrastructure.redis_ring import (
    RedisLiveLogRingBuffer,
)
from platform.features.support.ops.live_logs.infrastructure.stream_attach import (
    attach_live_log_handlers,
    reset_live_log_attach_state,
)
from platform.features.support.ops.live_logs.presentation.queries import (
    LiveLogRecentQuery,
)
from platform.features.support.ops.live_logs.presentation.realtime.consumer import (
    LiveLogsConsumer,
)

pytestmark = pytest.mark.unit


class _FakePipeline:
    def __init__(self, redis):
        self._redis = redis
        self._ops = []

    def lpush(self, key, value):
        self._ops.append(('lpush', key, value))
        return self

    def ltrim(self, key, start, end):
        self._ops.append(('ltrim', key, start, end))
        return self

    def expire(self, key, ttl):
        self._ops.append(('expire', key, ttl))
        return self

    def decr(self, key):
        self._ops.append(('decr', key))
        return self

    def execute(self):
        for op in self._ops:
            getattr(self._redis, op[0])(*op[1:])
        self._ops = []


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.ttls = {}
        self.fail = False

    def lpush(self, key, value):
        if self.fail:
            raise RuntimeError('redis down')
        self.store.setdefault(key, []).insert(0, value)

    def ltrim(self, key, start, end):
        data = self.store.get(key, [])
        self.store[key] = data[start:end + 1]

    def expire(self, key, ttl):
        self.ttls[key] = ttl

    def lrange(self, key, start, end):
        if self.fail:
            raise RuntimeError('redis down')
        data = self.store.get(key, [])
        if end == -1:
            return data[start:]
        return data[start:end + 1]

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0) or 0) + 1
        return self.store[key]

    def decr(self, key):
        self.store[key] = int(self.store.get(key, 0) or 0) - 1
        return self.store[key]

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value

    def pipeline(self):
        return _FakePipeline(self)


def _line(channel='api', level='INFO', message='hello', line_id='1'):
    return LiveLogLineView(
        id=line_id,
        ts=datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc),
        channel=channel,
        level=level,
        logger=f'app.{channel}',
        message=message,
        trace_id='abc',
        session_id='sess-1',
    )


def _record(name='app.request', level=logging.INFO, msg='>> REQ GET /x'):
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_catalog_maps_known_loggers():
    assert channel_for_logger('app.request').key == 'request'
    assert channel_for_logger('app.security').key == 'security'
    assert channel_for_logger('unknown') is None
    assert {c.key for c in LIVE_LOG_CHANNELS} >= {
        'request', 'api', 'security', 'errors', 'tasks', 'ai',
    }


def test_list_channels_use_case():
    result = ListLiveLogChannelsUseCase().execute()
    assert len(result.items) == len(LIVE_LOG_CHANNELS)
    assert result.levels == list(LEVEL_CHOICES)
    assert result.items[0].key == 'request'


def test_recent_use_case_delegates_to_ring():
    ring = MagicMock()
    ring.recent.return_value = [_line()]
    result = GetRecentLiveLogsUseCase(ring).execute(
        channel='api', min_level='WARNING', limit=10,
    )
    ring.recent.assert_called_once_with(channel='api', min_level='WARNING', limit=10)
    assert result.returned == 1
    assert result.items[0].message == 'hello'


def test_redis_ring_append_and_recent_filters():
    fake = FakeRedis()
    with patch.object(redis_ring, '_get_client', return_value=fake):
        buf = RedisLiveLogRingBuffer()
        buf.append(_line(channel='api', level='INFO', message='a', line_id='1'))
        buf.append(_line(channel='errors', level='ERROR', message='b', line_id='2'))
        buf.append(_line(channel='api', level='WARNING', message='c', line_id='3'))

        all_items = buf.recent(limit=10)
        assert [i.message for i in all_items] == ['a', 'b', 'c']

        only_api = buf.recent(channel='api', limit=10)
        assert [i.message for i in only_api] == ['a', 'c']

        warnings = buf.recent(min_level='WARNING', limit=10)
        assert [i.message for i in warnings] == ['b', 'c']


def test_redis_ring_down_returns_empty():
    fake = FakeRedis()
    fake.fail = True
    with patch.object(redis_ring, '_get_client', return_value=fake):
        buf = RedisLiveLogRingBuffer()
        assert buf.recent(limit=10) == []
        buf.append(_line())  # must not raise


@override_settings(LIVE_LOGS_CAPTURE_ASYNC=False)
def test_handler_emits_to_ring_and_publisher():
    ring = MagicMock()
    publisher = MagicMock()
    handler = LiveLogStreamHandler(publisher=publisher, ring=ring)
    handler.emit(_record())
    assert ring.append.call_count == 1
    assert publisher.emit_line.call_count == 1
    line = ring.append.call_args[0][0]
    assert line.channel == 'request'
    assert line.message == '>> REQ GET /x'
    assert line.level == 'INFO'
    # uuid7 string form
    assert len(line.id) >= 32


@override_settings(LIVE_LOGS_CAPTURE_ASYNC=False)
def test_handler_includes_session_id_from_context():
    ring = MagicMock()
    publisher = MagicMock()
    handler = LiveLogStreamHandler(publisher=publisher, ring=ring)
    with patch(
        'platform.features.support.ops.live_logs.infrastructure.live_log_handler.get_session_id',
        return_value='sid-xyz',
    ), patch(
        'platform.features.support.ops.live_logs.infrastructure.live_log_handler.get_username',
        return_value='sebastian.narvaez',
    ):
        handler.emit(_record(msg='>> REQ GET /y'))
    line = ring.append.call_args[0][0]
    assert line.session_id == 'sid-xyz'
    assert line.username == 'sebastian.narvaez'


@override_settings(LIVE_LOGS_CAPTURE_ASYNC=False)
def test_handler_ignores_unknown_logger():
    ring = MagicMock()
    publisher = MagicMock()
    handler = LiveLogStreamHandler(publisher=publisher, ring=ring)
    handler.emit(_record(name='django.request', level=logging.ERROR, msg='boom'))
    ring.append.assert_not_called()
    publisher.emit_line.assert_not_called()


@override_settings(LIVE_LOGS_CAPTURE_ASYNC=False, LIVE_LOGS_MAX_MESSAGE_CHARS=20)
def test_handler_truncates_long_messages():
    ring = MagicMock()
    publisher = MagicMock()
    handler = LiveLogStreamHandler(publisher=publisher, ring=ring)
    handler.emit(_record(msg='x' * 50))
    line = ring.append.call_args[0][0]
    assert len(line.message) == 20
    assert line.message.endswith('…')


@override_settings(LIVE_LOGS_CAPTURE_ASYNC=False)
def test_handler_redacts_embedded_json_secrets():
    ring = MagicMock()
    publisher = MagicMock()
    handler = LiveLogStreamHandler(publisher=publisher, ring=ring)
    handler.emit(_record(msg='body={"password":"secret","ok":1}'))
    line = ring.append.call_args[0][0]
    assert 'secret' not in line.message
    assert '***' in line.message


@override_settings(LIVE_LOGS_CAPTURE_ASYNC=False)
def test_handler_reentrancy_guard():
    ring = MagicMock()
    publisher = MagicMock()

    def _append_side_effect(line):
        # Nested emit while fan-out is active must be ignored.
        handler.emit(_record(msg='nested'))

    ring.append.side_effect = _append_side_effect
    handler = LiveLogStreamHandler(publisher=publisher, ring=ring)
    handler.emit(_record())
    assert ring.append.call_count == 1


def test_recent_query_rejects_bad_channel_and_over_limit():
    _, err = LiveLogRecentQuery({'channel': 'nope'}).parse()
    assert err is not None

    _, err_limit = LiveLogRecentQuery({'limit': '9999'}).parse()
    assert err_limit is not None


def test_recent_query_accepts_valid_filters():
    pq, err = LiveLogRecentQuery({
        'channel': 'api', 'level': 'WARNING', 'limit': '10',
    }).parse()
    assert err is None
    assert pq is not None
    assert pq.filters['channel'] == 'api'
    assert pq.filters['level'] == 'WARNING'
    assert pq.filters['limit'] == 10
    assert LiveLogRecentQuery.limit.max_value == 500


@override_settings(LIVE_LOGS_ENABLED=True, LIVE_LOGS_MIN_LEVEL='INFO')
def test_attach_handlers_is_idempotent():
    reset_live_log_attach_state()
    lg = logging.getLogger('app.request')
    before = sum(1 for h in lg.handlers if isinstance(h, LiveLogStreamHandler))
    first = attach_live_log_handlers()
    second = attach_live_log_handlers()
    after = sum(1 for h in lg.handlers if isinstance(h, LiveLogStreamHandler))
    assert first is not None
    assert second is first
    # Never double-attach beyond whatever dictConfig already installed.
    assert after == max(before, 1)


@override_settings(LIVE_LOGS_ENABLED=True, LIVE_LOGS_MIN_LEVEL='INFO')
def test_attach_handlers_reinstalls_after_logging_reconfig():
    """Un dictConfig posterior (segundo django.setup de runserver) quita el handler."""
    reset_live_log_attach_state()
    first = attach_live_log_handlers()
    assert first is not None

    for channel_name in ('app.request', 'app.api', 'app.security', 'app.errors', 'app.tasks', 'app.ai'):
        lg = logging.getLogger(channel_name)
        lg.handlers = [h for h in lg.handlers if not isinstance(h, LiveLogStreamHandler)]

    lg = logging.getLogger('app.request')
    assert not any(isinstance(h, LiveLogStreamHandler) for h in lg.handlers)

    second = attach_live_log_handlers()
    assert second is first
    assert any(h is first for h in lg.handlers)


def test_ws_consumer_rejects_non_admin():
    import asyncio

    consumer = LiveLogsConsumer()
    consumer.scope = {'audience': 'client', 'user': object(), 'tenant_schema': 'public'}
    consumer.close = AsyncMock()
    consumer.accept = AsyncMock()

    asyncio.get_event_loop().run_until_complete(consumer.connect())
    consumer.close.assert_awaited_once_with(code=4401)
    consumer.accept.assert_not_awaited()


def test_publisher_skips_when_no_subscribers():
    from platform.features.support.ops.live_logs.infrastructure.realtime_publisher import (
        LiveLogsRealtimePublisher,
    )

    inner = MagicMock()
    pub = LiveLogsRealtimePublisher(publisher=inner)
    with patch(
        'platform.features.support.ops.live_logs.infrastructure.realtime_publisher.live_log_subscriber_count',
        return_value=0,
    ):
        pub.emit_line(_line())
    inner.to_group.assert_not_called()

    with patch(
        'platform.features.support.ops.live_logs.infrastructure.realtime_publisher.live_log_subscriber_count',
        return_value=2,
    ):
        pub.emit_line(_line())
    inner.to_group.assert_called_once()


@override_settings(SECRET_KEY='test-secret-key')
def test_bind_actor_from_jwt_uses_username_claim_and_verifies_exp():
    from core.auth.jwt_service import create_access_token
    from core.auth.cookies import ACCESS_ADMIN_COOKIE
    from core.trace import bind_actor_from_request, get_user_id, get_username, set_user_id, set_username
    from django.test import RequestFactory

    set_username('')
    set_user_id('')
    with patch('core.auth.jwt_service.get_access_ttl_minutes', return_value=30):
        token = create_access_token(
            user_id='admin-9',
            user_type='admin',
            username='obs.admin',
        )
    request = RequestFactory().get('/')
    request.COOKIES = {ACCESS_ADMIN_COOKIE: token}
    request.user = MagicMock(is_authenticated=False)
    request.META['HTTP_X_AUTH_CONTEXT'] = 'admin'
    bind_actor_from_request(request)
    assert get_user_id() == 'admin-9'
    assert get_username() == 'obs.admin'
