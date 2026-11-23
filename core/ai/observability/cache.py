"""
core/ai/observability/cache.py
───────────────────────────────
Caché e idempotencia de completions de IA.

Motivo: las llamadas a un LLM tienen costo y latencia. Prompts equivalentes no
deberían pagarse dos veces. La caché es opcional (``settings.AI_CACHE_ENABLED``)
y se apoya en el backend Redis 'access' del proyecto (IGNORE_EXCEPTIONS=True →
si Redis cae, la caché simplemente no acierta, nunca rompe el flujo).

La clave se deriva de un hash estable del prompt + modelo, por lo que es
determinista y no expone el contenido. El aislamiento por tenant se logra
prefijando con el schema activo, de modo que dos empresas nunca comparten
respuestas cacheadas.
"""

import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import caches
from django.db import connection

from ..domain.schemas import Completion, Prompt

logger = logging.getLogger('app.ai')

_CACHE_ALIAS = 'access'   # backend Redis con IGNORE_EXCEPTIONS=True
_KEY_PREFIX = 'ai:completion'


def _cache():
    try:
        return caches[_CACHE_ALIAS]
    except Exception:
        return None


def _tenant() -> str:
    try:
        return getattr(connection, 'schema_name', 'public') or 'public'
    except Exception:
        return 'public'


def cache_key(prompt: Prompt, model: str) -> str:
    """Clave determinista y aislada por tenant para un (prompt, model)."""
    payload = {
        'system': prompt.system,
        'messages': [(m.role.value, m.content) for m in prompt.messages],
        'model': model,
        'max_tokens': prompt.options.max_tokens,
        'temperature': prompt.options.temperature,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
    ).hexdigest()
    return f'{_KEY_PREFIX}:{_tenant()}:{digest}'


def is_enabled(prompt: Prompt) -> bool:
    """
    La caché solo aplica a generaciones deterministas (temperature == 0),
    porque cachear salidas creativas daría respuestas idénticas donde se
    espera variación.
    """
    if not getattr(settings, 'AI_CACHE_ENABLED', False):
        return False
    temp = prompt.options.temperature
    return temp is None or temp == 0


def get_cached(prompt: Prompt, model: str) -> Completion | None:
    if not is_enabled(prompt):
        return None
    cache = _cache()
    if cache is None:
        return None
    try:
        raw = cache.get(cache_key(prompt, model))
        return Completion(**raw) if raw else None
    except Exception:
        return None


def set_cached(prompt: Prompt, model: str, completion: Completion) -> None:
    if not is_enabled(prompt) or completion.degraded:
        return
    cache = _cache()
    if cache is None:
        return
    try:
        ttl = getattr(settings, 'AI_CACHE_TTL_SECONDS', 3600)
        cache.set(cache_key(prompt, model), completion.model_dump(mode='json'), ttl)
    except Exception:
        pass
