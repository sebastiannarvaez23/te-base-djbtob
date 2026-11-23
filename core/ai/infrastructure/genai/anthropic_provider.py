"""
core/ai/infrastructure/anthropic_provider.py
──────────────────────────────────────────────
Adaptador de IChatModel usando la API de Anthropic (Claude) — proveedor
gestionado inicial (cubo 1: GenAI texto).

Configuración (base/settings/base.py → .env):
    AI_PROVIDER='anthropic'
    AI_API_KEY          — clave de API del proveedor
    AI_CHAT_MODEL       — id de modelo (default 'claude-opus-4-8')
    AI_MAX_TOKENS       — tope de tokens de salida (default 4096)
    AI_TIMEOUT_SECONDS  — timeout por llamada (default 30)

El SDK ``anthropic`` se importa de forma perezosa: la app no requiere la
dependencia salvo que este proveedor esté activo. Los errores del SDK se
normalizan a la jerarquía AppException con códigos AI_*.

Notas de la API (ver skill claude-api):
- Modelos Opus 4.8/4.7 y Sonnet 5 usan thinking adaptativo y NO aceptan
  ``temperature`` (devuelve 400); por eso este adaptador no envía sampling
  params por defecto.
- La respuesta trae ``content`` como lista de bloques; se concatenan los de
  tipo 'text'. El uso de tokens viene en ``response.usage``.
"""

import logging
from typing import Iterator, Tuple

from django.conf import settings

from core.errors import AppErrorCode, ServerException

from ...domain.genai.schemas import FinishReason, MessageRole, Prompt, TokenUsage
from .base import BaseChatModel

logger = logging.getLogger('app.ai')

_FINISH_MAP = {
    'end_turn': FinishReason.STOP,
    'stop_sequence': FinishReason.STOP,
    'max_tokens': FinishReason.LENGTH,
    'refusal': FinishReason.STOP,
}


class AnthropicChatModel(BaseChatModel):
    """Adaptador de chat sobre la API de Anthropic (Claude)."""

    provider_name = 'anthropic'

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        max_tokens: int | None = None,
        timeout_s: float | None = None,
    ):
        configured = model or getattr(settings, 'AI_CHAT_MODEL', '') or ''
        # Default local del settings es un tag SLM; si el caller no pasó modelo
        # cloud, usar Claude de referencia.
        if not configured or configured.startswith(('qwen', 'llama', 'phi', 'mistral', 'gemma')):
            configured = 'claude-opus-4-8'
        self.model_name = configured
        self._max_tokens = max_tokens if max_tokens is not None else getattr(settings, 'AI_MAX_TOKENS', 4096)
        self._timeout = timeout_s if timeout_s is not None else getattr(settings, 'AI_TIMEOUT_SECONDS', 30)
        self._api_key = api_key
        self._client = self._build_client()

    def _build_client(self):
        try:
            import anthropic
        except ImportError as exc:
            raise ServerException(
                AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                override_detail="The 'anthropic' SDK is not installed. "
                                "Add it to requiriments.txt or change AI_PROVIDER.",
            ) from exc
        api_key = self._api_key or getattr(settings, 'AI_API_KEY', '') or None
        if not api_key:
            raise ServerException(
                AppErrorCode.AI_PROVIDER_UNAVAILABLE,
                override_detail='AI_API_KEY is not configured for the Anthropic provider.',
            )
        return anthropic.Anthropic(api_key=api_key, timeout=self._timeout)

    # ── Traducción de dominio → API ────────────────────────────────────────────

    def _to_api_messages(self, prompt: Prompt) -> list[dict]:
        """Convierte los mensajes del dominio al formato de la API (excluye system)."""
        return [
            {'role': m.role.value, 'content': m.content}
            for m in prompt.messages
            if m.role != MessageRole.SYSTEM
        ]

    def _resolve(self, prompt: Prompt) -> Tuple[str, int]:
        model = prompt.options.model or self.model_name
        max_tokens = prompt.options.max_tokens or self._max_tokens
        return model, max_tokens

    # ── Generación ──────────────────────────────────────────────────────────────

    def _generate(self, prompt: Prompt) -> Tuple[str, TokenUsage, FinishReason]:
        import anthropic

        model, max_tokens = self._resolve(prompt)
        kwargs = {
            'model': model,
            'max_tokens': max_tokens,
            'messages': self._to_api_messages(prompt),
        }
        if prompt.system:
            kwargs['system'] = prompt.system

        try:
            response = self._client.messages.create(**kwargs)
        except anthropic.APITimeoutError as exc:
            raise ServerException(AppErrorCode.AI_TIMEOUT, override_detail=str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise ServerException(AppErrorCode.AI_QUOTA_EXCEEDED, override_detail=str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise ServerException(AppErrorCode.AI_PROVIDER_UNAVAILABLE, override_detail=str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise ServerException(AppErrorCode.AI_PROVIDER_ERROR, override_detail=str(exc)) from exc

        text = ''.join(
            block.text for block in response.content if getattr(block, 'type', None) == 'text'
        )
        usage = TokenUsage(
            input_tokens=getattr(response.usage, 'input_tokens', 0),
            output_tokens=getattr(response.usage, 'output_tokens', 0),
        )
        finish = _FINISH_MAP.get(getattr(response, 'stop_reason', ''), FinishReason.UNKNOWN)
        return text, usage, finish

    # ── Streaming nativo ─────────────────────────────────────────────────────────

    def stream(self, prompt: Prompt) -> Iterator[str]:
        import anthropic
        from time import perf_counter

        from ...observability.usage_tracker import record_usage
        from ...safety import redact_prompt

        outgoing = redact_prompt(prompt) if getattr(settings, 'AI_REDACT_PROMPTS', True) else prompt
        model, max_tokens = self._resolve(outgoing)
        kwargs = {
            'model': model,
            'max_tokens': max_tokens,
            'messages': self._to_api_messages(outgoing),
        }
        if outgoing.system:
            kwargs['system'] = outgoing.system

        pieces: list[str] = []
        start = perf_counter()
        try:
            with self._client.messages.stream(**kwargs) as stream:
                for delta in stream.text_stream:
                    pieces.append(delta)
                    yield delta
        except anthropic.APITimeoutError as exc:
            raise ServerException(AppErrorCode.AI_TIMEOUT, override_detail=str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise ServerException(AppErrorCode.AI_PROVIDER_ERROR, override_detail=str(exc)) from exc
        finally:
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
