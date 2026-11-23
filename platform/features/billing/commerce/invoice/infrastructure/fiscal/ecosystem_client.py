"""Process-wide ``EcosystemClient`` for Neurana (pooled HTTP + shared breaker).

One client per worker process: keep-alive connections, cached access token
and a circuit breaker whose state lives in the Django cache (Redis), so every
worker opens / closes together and only one probe runs while half-open.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from django.conf import settings

from core.trace import get_trace_id

logger = logging.getLogger('billing.invoice.fiscal')

BREAKER_NAME = 'neurana'

_lock = threading.Lock()
_client = None


def _signing_key():
    from necore.ecosystem.keys import SigningKey, load_private_key

    pem = (getattr(settings, 'NE_PRODUCT_PRIVATE_KEY', '') or '').strip()
    path = (getattr(settings, 'NE_PRODUCT_PRIVATE_KEY_FILE', '') or '').strip()
    if not pem and path and Path(path).is_file():
        pem = Path(path).read_text(encoding='ascii')
    if not pem:
        return None
    return SigningKey.from_private(load_private_key(pem))


def _on_breaker_transition(previous: str, new: str, state) -> None:
    try:
        from platform.features.billing.commerce.fiscal_outbox.infrastructure.alert_notifier import (
            FiscalSyncAlertNotifier,
        )

        FiscalSyncAlertNotifier().breaker_changed(previous=previous, new=new)
    except Exception:  # noqa: BLE001 — alerts must never break the fiscal path
        logger.exception('fiscal_breaker_alert_failed %s->%s', previous, new)


def build_breaker():
    from necore.ecosystem.breaker import CacheBreakerStore, CircuitBreaker

    return CircuitBreaker(
        BREAKER_NAME,
        store=CacheBreakerStore(),
        failure_threshold=int(getattr(settings, 'NE_BREAKER_FAILURE_THRESHOLD', 5)),
        cooldown_seconds=float(getattr(settings, 'NE_BREAKER_COOLDOWN_SECONDS', 30)),
        max_cooldown_seconds=float(getattr(settings, 'NE_BREAKER_MAX_COOLDOWN_SECONDS', 300)),
        on_transition=_on_breaker_transition,
    )


def build_ecosystem_client():
    from necore.ecosystem import EcosystemClient

    return EcosystemClient(
        base_url=getattr(settings, 'NE_ECOSYSTEM_BASE_URL', ''),
        product=getattr(settings, 'NE_PRODUCT_CODE', 'base'),
        client_id=getattr(settings, 'NE_PRODUCT_CLIENT_ID', ''),
        client_secret=getattr(settings, 'NE_PRODUCT_CLIENT_SECRET', ''),
        signing_key=_signing_key(),
        connect_timeout_seconds=float(getattr(settings, 'NE_CONNECT_TIMEOUT_SECONDS', 2)),
        read_timeout_seconds=float(getattr(settings, 'NE_READ_TIMEOUT_SECONDS', 8)),
        max_retries=int(getattr(settings, 'NE_HTTP_MAX_RETRIES', 2)),
        breaker=build_breaker(),
        allow_insecure=bool(getattr(settings, 'NE_ALLOW_INSECURE_HTTP', False)),
        trace_id_provider=get_trace_id,
    )


def get_ecosystem_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = build_ecosystem_client()
    return _client


def reset_ecosystem_client() -> None:
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:  # noqa: BLE001
                pass
        _client = None
