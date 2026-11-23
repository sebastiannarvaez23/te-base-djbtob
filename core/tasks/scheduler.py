"""Celery Beat scheduler: RedBeat with lock recovery.

Upstream RedBeat treats Redis lock loss as a fatal HA failover: the
process exits so a *replica* Beat can win the election. That model
assumes multiple Beat processes and intentional failover.

The base runs a **single Beat** per environment (local, Docker Desktop,
one production replica). In that topology, lock loss from Windows sleep,
container pause, or Redis restart would kill the only scheduler instead
of recovering. ``BaseRedBeatScheduler`` re-acquires ``redbeat::lock``
and keeps ticking.

HA tradeoff (documented on purpose):
  * Single-Beat + this recovery = resilience to pause/restart; do **not**
    run two Beats with this subclass or both may schedule after a lock
    fight (duplicate firings mitigated by per-task Redis locks +
    ``expires``, but still wasteful).
  * Multi-Beat HA = use stock ``RedBeatScheduler`` (exit on lock loss)
    so only one elected process ticks.
"""

from celery.utils.log import get_logger
from redis.exceptions import LockError, LockNotOwnedError
from redbeat.schedulers import LUA_EXTEND_TO_SCRIPT, RedBeatScheduler, get_redis

logger = get_logger('celery.beat')


class BaseRedBeatScheduler(RedBeatScheduler):
    """RedBeat scheduler that survives losing the distributed lock.

    Intended for single-Beat deployments only; see module docstring.
    """

    def tick(self, **kwargs):
        lock_key = self.lock_key
        if lock_key:
            self._renew_lock()
            # Parent ``tick`` extends the lock and crashes on
            # ``LockNotOwnedError``. We already renewed; skip that path.
            self.lock_key = None
        try:
            return super().tick(**kwargs)
        finally:
            self.lock_key = lock_key

    def _renew_lock(self):
        try:
            if self.lock is not None:
                logger.debug('beat: Extending lock...')
                self.lock.extend(int(self.lock_timeout))
                return
        except (LockNotOwnedError, LockError):
            logger.warning(
                'beat: Redis lock lost (process paused, Redis restarted, '
                'or TTL expired). Re-acquiring (single-Beat recovery).'
            )
            self._drop_stale_lock()
        self._acquire_lock()

    def _drop_stale_lock(self):
        lock = self.lock
        self.lock = None
        if lock is None:
            return
        try:
            lock.release()
        except (LockNotOwnedError, LockError):
            pass

    def _acquire_lock(self):
        redis_client = get_redis(self.app)
        lock = redis_client.lock(
            self.lock_key,
            timeout=self.lock_timeout,
            sleep=self.max_interval,
        )
        # Same override as redbeat.schedulers.acquire_distributed_beat_lock:
        # redis-py's default extend *adds* TTL; this script *replaces* it.
        lock.lua_extend = redis_client.register_script(LUA_EXTEND_TO_SCRIPT)
        lock.acquire()
        logger.info('beat: Acquired lock')
        self.lock = lock
