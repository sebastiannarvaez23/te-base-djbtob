"""Catálogo de canales de log en vivo (logger Python → canal admin)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiveLogChannelDef:
    key: str
    logger_name: str
    label: str
    icon: str
    description: str


# Canales expuestos al admin. El handler se adjunta a cada ``logger_name``.
LIVE_LOG_CHANNELS: tuple[LiveLogChannelDef, ...] = (
    LiveLogChannelDef(
        key='request',
        logger_name='app.request',
        label='Request',
        icon='bx-transfer',
        description='HTTP request/response traces',
    ),
    LiveLogChannelDef(
        key='api',
        logger_name='app.api',
        label='API',
        icon='bx-server',
        description='General API traffic',
    ),
    LiveLogChannelDef(
        key='security',
        logger_name='app.security',
        label='Security',
        icon='bx-shield-quarter',
        description='Auth and permission events',
    ),
    LiveLogChannelDef(
        key='errors',
        logger_name='app.errors',
        label='Errors',
        icon='bx-error-circle',
        description='Application and business errors',
    ),
    LiveLogChannelDef(
        key='tasks',
        logger_name='app.tasks',
        label='Tasks',
        icon='bx-cog',
        description='Celery / background task logs',
    ),
    LiveLogChannelDef(
        key='ai',
        logger_name='app.ai',
        label='AI',
        icon='bx-brain',
        description='AI usage and fallbacks',
    ),
)

_BY_LOGGER = {c.logger_name: c for c in LIVE_LOG_CHANNELS}
_BY_KEY = {c.key: c for c in LIVE_LOG_CHANNELS}

LEVEL_ORDER = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50,
}

LEVEL_CHOICES = tuple(LEVEL_ORDER.keys())


def channel_for_logger(logger_name: str) -> LiveLogChannelDef | None:
    return _BY_LOGGER.get(logger_name)


def channel_by_key(key: str) -> LiveLogChannelDef | None:
    return _BY_KEY.get(key)


def all_channel_keys() -> tuple[str, ...]:
    return tuple(c.key for c in LIVE_LOG_CHANNELS)
