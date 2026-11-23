"""Sonda de salud del runtime de inferencia (best-effort)."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from urllib.parse import urljoin

from django.conf import settings

logger = logging.getLogger('app.ai')


class RuntimeHealthProbe:
    """Adaptador concreto: ``ok`` | ``down`` | ``unknown``."""

    def probe(self, provider: str) -> str:
        name = (provider or '').lower()
        if name == 'fake':
            return 'ok'
        if name in ('anthropic', 'openai'):
            key = (
                getattr(settings, 'AI_API_KEY', '')
                or getattr(settings, 'OPENAI_API_KEY', '')
                or ''
            ).strip()
            return 'ok' if key else 'unknown'
        if name != 'local':
            return 'unknown'
        return self._probe_local_runtime()

    def _probe_local_runtime(self) -> str:
        base = (
            (getattr(settings, 'AI_RUNTIME_URL', 'http://127.0.0.1:3310') or '')
            .rstrip('/')
            + '/'
        )
        url = urljoin(base, 'v1/models')
        req = urllib.request.Request(url, method='GET', headers={'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if 200 <= getattr(resp, 'status', 200) < 300:
                    return 'ok'
                return 'down'
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.info('AI runtime health probe failed: %s', exc)
            return 'down'


def probe_inference_health(provider: str) -> str:
    """Atajo funcional (tests / callers simples)."""
    return RuntimeHealthProbe().probe(provider)
