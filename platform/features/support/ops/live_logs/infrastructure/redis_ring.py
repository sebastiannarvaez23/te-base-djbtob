"""Redis ring buffer of recent live-log lines (catch-up on connect)."""

from __future__ import annotations

import json
import logging

from django.conf import settings

from platform.features.support.ops.live_logs.domain.catalog import LEVEL_ORDER
from platform.features.support.ops.live_logs.domain.interfaces import ILiveLogRingBuffer
from platform.features.support.ops.live_logs.domain.schemas import LiveLogLineView

logger = logging.getLogger('app.api')

_KEY = 'live_logs:ring'
_SUB_KEY = 'live_logs:subscribers'


def _get_client():
    from django_redis import get_redis_connection
    return get_redis_connection('observability')


def incr_live_log_subscribers() -> None:
    try:
        _get_client().incr(_SUB_KEY)
    except Exception:
        pass


def decr_live_log_subscribers() -> None:
    try:
        client = _get_client()
        pipe = client.pipeline()
        pipe.decr(_SUB_KEY)
        pipe.execute()
        val = int(client.get(_SUB_KEY) or 0)
        if val < 0:
            client.set(_SUB_KEY, 0)
    except Exception:
        pass


def live_log_subscriber_count() -> int:
    try:
        raw = _get_client().get(_SUB_KEY)
        return max(0, int(raw or 0))
    except Exception:
        # Fail open: publisher still fans out if counter is unavailable.
        return 1


class RedisLiveLogRingBuffer(ILiveLogRingBuffer):

    def __init__(self):
        self._ring_size = int(getattr(settings, 'LIVE_LOGS_RING_SIZE', 500))
        self._ttl = int(getattr(settings, 'LIVE_LOGS_RING_TTL_SECONDS', 3600))

    def append(self, line: LiveLogLineView) -> None:
        try:
            payload = json.dumps(line.model_dump(mode='json'), ensure_ascii=False)
            client = _get_client()
            pipe = client.pipeline()
            pipe.lpush(_KEY, payload)
            pipe.ltrim(_KEY, 0, self._ring_size - 1)
            pipe.expire(_KEY, self._ttl)
            pipe.execute()
        except Exception as exc:
            logger.warning('LIVE_LOGS_RING_APPEND_FAILED error=%s', exc)

    def recent(
        self,
        *,
        channel: str | None = None,
        min_level: str | None = None,
        limit: int = 100,
    ) -> list[LiveLogLineView]:
        try:
            raw = _get_client().lrange(_KEY, 0, self._ring_size - 1)
        except Exception as exc:
            logger.warning('LIVE_LOGS_RING_SNAPSHOT_FAILED error=%s', exc)
            return []

        min_rank = LEVEL_ORDER.get((min_level or '').upper(), 0)
        items: list[LiveLogLineView] = []
        for item in raw:
            if isinstance(item, bytes):
                item = item.decode('utf-8', errors='replace')
            try:
                data = json.loads(item)
                line = LiveLogLineView.model_validate(data)
            except (ValueError, TypeError):
                continue
            if channel and line.channel != channel:
                continue
            if min_rank and LEVEL_ORDER.get(line.level.upper(), 0) < min_rank:
                continue
            items.append(line)
            if len(items) >= limit:
                break

        # LPUSH leaves newest first; reverse to chronological for the UI.
        items.reverse()
        return items
