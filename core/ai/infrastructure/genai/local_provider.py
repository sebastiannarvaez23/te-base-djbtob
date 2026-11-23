"""
core/ai/infrastructure/local_provider.py
──────────────────────────────────────────
Adaptador de IChatModel hacia un **runtime SLM nativo** (proceso aparte).

Habla HTTP con la API **OpenAI-compatible** del runtime (Ollama, llama.cpp
server, etc.):

    POST {AI_RUNTIME_URL}/v1/chat/completions

Configuración (base/settings/base.py → .env):
    AI_PROVIDER='local'
    AI_RUNTIME_URL      — default http://127.0.0.1:3310
    AI_CHAT_MODEL       — id del modelo en el runtime (ej. qwen2.5:1.5b)
    AI_MAX_TOKENS       — tope de salida (default más bajo vía settings locales)
    AI_TIMEOUT_SECONDS  — timeout por llamada
    AI_MAX_CONCURRENT   — semáforo de inferencias simultáneas (protege CPU/RAM)

Sin reintentos agresivos: un fallo de red/timeout se mapea a AI_* y el caller
usa ``complete_or`` / degradación. Si ``AI_ENABLED=False``, el factory no debe
instanciar este adaptador (ver ``config.get_chat_model``).

Ver ``docs/plan-ia/fase-0b-runtime-slm.md``.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Iterator, Tuple
from urllib.parse import urljoin

from django.conf import settings

from core.errors import AppErrorCode, ServerException

from ...domain.genai.schemas import FinishReason, MessageRole, Prompt, TokenUsage
from .base import BaseChatModel

logger = logging.getLogger('app.ai')

# Modelo SLM por defecto (CPU, ~1–2B cuantizado). Override con AI_CHAT_MODEL.
_DEFAULT_LOCAL_MODEL = 'qwen2.5:1.5b'

_FINISH_MAP = {
    'stop': FinishReason.STOP,
    'length': FinishReason.LENGTH,
    'max_tokens': FinishReason.LENGTH,
}

# Semáforo de proceso: un runtime compartido no debe saturar el host.
_infer_lock = threading.Lock()
_infer_sema: threading.BoundedSemaphore | None = None
_infer_sema_n: int | None = None


def _concurrency_sema() -> threading.BoundedSemaphore:
    global _infer_sema, _infer_sema_n
    n = max(1, int(getattr(settings, 'AI_MAX_CONCURRENT', 1)))
    with _infer_lock:
        if _infer_sema is None or _infer_sema_n != n:
            _infer_sema = threading.BoundedSemaphore(n)
            _infer_sema_n = n
        return _infer_sema


def _resolve_model_name(explicit: str | None) -> str:
    """Evita mandar ids de cloud (claude/gpt) al runtime local por accidente."""
    if explicit:
        return explicit
    configured = (getattr(settings, 'AI_CHAT_MODEL', '') or '').strip()
    if not configured or configured.startswith(('claude', 'gpt-')):
        return _DEFAULT_LOCAL_MODEL
    return configured


class LocalChatModel(BaseChatModel):
    """IChatModel sobre runtime SLM local (OpenAI-compatible HTTP)."""

    provider_name = 'local'

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model_name = _resolve_model_name(model)
        self._base_url = (
            (base_url or getattr(settings, 'AI_RUNTIME_URL', 'http://127.0.0.1:3310'))
            .rstrip('/')
            + '/'
        )
        self._max_tokens = int(getattr(settings, 'AI_MAX_TOKENS', 1024))
        self._timeout = float(getattr(settings, 'AI_TIMEOUT_SECONDS', 60.0))

    def _chat_url(self) -> str:
        return urljoin(self._base_url, 'v1/chat/completions')

    def _to_api_messages(self, prompt: Prompt) -> list[dict]:
        messages: list[dict] = []
        if prompt.system:
            messages.append({'role': 'system', 'content': prompt.system})
        for m in prompt.messages:
            if m.role == MessageRole.SYSTEM:
                # Ya cubierto por prompt.system; evita duplicar si viene en messages.
                if not prompt.system:
                    messages.append({'role': 'system', 'content': m.content})
                continue
            messages.append({'role': m.role.value, 'content': m.content})
        return messages

    def _resolve(self, prompt: Prompt) -> Tuple[str, int, float]:
        model = prompt.options.model or self.model_name
        if model.startswith(('claude', 'gpt-')):
            model = _DEFAULT_LOCAL_MODEL
        max_tokens = prompt.options.max_tokens or self._max_tokens
        timeout = prompt.options.timeout_seconds or self._timeout
        return model, max_tokens, float(timeout)

    def _post_json(self, body: dict, timeout: float) -> dict:
        payload = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(
            self._chat_url(),
            data=payload,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace') if exc.fp else str(exc)
            if exc.code == 404:
                raise ServerException(
                    AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                    override_detail=(
                        f'Runtime chat endpoint not found ({self._chat_url()}). '
                        f'Is ai-runtime up? Detail: {detail[:400]}'
                    ),
                ) from exc
            raise ServerException(
                AppErrorCode.AI_PROVIDER_ERROR,
                override_detail=f'Runtime HTTP {exc.code}: {detail[:400]}',
            ) from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, 'reason', exc)
            raise ServerException(
                AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                override_detail=(
                    f'AI runtime unreachable at {self._base_url}: {reason}. '
                    'Start it with: docker compose --profile ai up -d'
                ),
            ) from exc
        except TimeoutError as exc:
            raise ServerException(
                AppErrorCode.AI_TIMEOUT,
                override_detail=str(exc),
            ) from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ServerException(
                AppErrorCode.AI_INVALID_RESPONSE,
                override_detail=f'Runtime returned non-JSON: {raw[:200]}',
            ) from exc

    def _parse_completion(self, data: dict) -> Tuple[str, TokenUsage, FinishReason]:
        choices = data.get('choices') or []
        if not choices:
            raise ServerException(
                AppErrorCode.AI_INVALID_RESPONSE,
                override_detail='Runtime returned no choices.',
            )
        choice = choices[0]
        message = choice.get('message') or {}
        text = (message.get('content') or '').strip()
        if not text:
            raise ServerException(
                AppErrorCode.AI_INVALID_RESPONSE,
                override_detail='Runtime returned an empty message.',
            )
        usage_raw = data.get('usage') or {}
        usage = TokenUsage(
            input_tokens=int(usage_raw.get('prompt_tokens') or 0),
            output_tokens=int(usage_raw.get('completion_tokens') or 0),
        )
        finish = _FINISH_MAP.get(
            (choice.get('finish_reason') or '').lower(),
            FinishReason.UNKNOWN,
        )
        return text, usage, finish

    def _generate(self, prompt: Prompt) -> Tuple[str, TokenUsage, FinishReason]:
        model, max_tokens, timeout = self._resolve(prompt)
        body = {
            'model': model,
            'messages': self._to_api_messages(prompt),
            'max_tokens': max_tokens,
            'stream': False,
        }
        if prompt.options.temperature is not None:
            body['temperature'] = prompt.options.temperature

        sema = _concurrency_sema()
        if not sema.acquire(blocking=True, timeout=timeout):
            raise ServerException(
                AppErrorCode.AI_QUOTA_EXCEEDED,
                override_detail='AI inference concurrency limit reached; try again later.',
            )
        try:
            data = self._post_json(body, timeout=timeout)
            return self._parse_completion(data)
        finally:
            sema.release()

    def stream(self, prompt: Prompt) -> Iterator[str]:
        """
        Streaming SSE (OpenAI-compatible). Si el runtime no soporta stream,
        cae al comportamiento de BaseChatModel (una sola pieza).
        """
        from time import perf_counter

        from ...observability.usage_tracker import record_usage
        from ...safety import redact_prompt

        outgoing = redact_prompt(prompt) if getattr(settings, 'AI_REDACT_PROMPTS', True) else prompt
        model, max_tokens, timeout = self._resolve(outgoing)
        body = {
            'model': model,
            'messages': self._to_api_messages(outgoing),
            'max_tokens': max_tokens,
            'stream': True,
        }
        if outgoing.options.temperature is not None:
            body['temperature'] = outgoing.options.temperature

        payload = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(
            self._chat_url(),
            data=payload,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
        )

        sema = _concurrency_sema()
        if not sema.acquire(blocking=True, timeout=timeout):
            raise ServerException(
                AppErrorCode.AI_QUOTA_EXCEEDED,
                override_detail='AI inference concurrency limit reached; try again later.',
            )
        pieces: list[str] = []
        start = perf_counter()
        try:
            try:
                resp = urllib.request.urlopen(req, timeout=timeout)
            except urllib.error.URLError as exc:
                raise ServerException(
                    AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                    override_detail=f'AI runtime unreachable: {getattr(exc, "reason", exc)}',
                ) from exc

            with resp as stream:
                for raw_line in stream:
                    line = raw_line.decode('utf-8', errors='replace').strip()
                    if not line or not line.startswith('data:'):
                        continue
                    data_str = line[5:].strip()
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get('choices') or []
                    if not choices:
                        continue
                    delta = (choices[0].get('delta') or {}).get('content') or ''
                    if delta:
                        pieces.append(delta)
                        yield delta
        finally:
            sema.release()
            text = ''.join(pieces)
            if text:
                input_len = sum(len(m.content) for m in outgoing.messages) + len(outgoing.system or '')
                record_usage(
                    provider=self.provider_name,
                    model=model,
                    usage=TokenUsage(
                        input_tokens=max(1, input_len // 4),
                        output_tokens=max(1, len(text) // 4),
                    ),
                    latency_ms=int((perf_counter() - start) * 1000),
                    feature=outgoing.options.metadata.get('feature', '-'),
                )
