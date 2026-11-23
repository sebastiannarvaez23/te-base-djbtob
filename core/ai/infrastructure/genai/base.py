"""
core/ai/infrastructure/base.py
────────────────────────────────
Clase base para adaptadores de chat (IChatModel).

Centraliza el flujo transversal común a todos los proveedores para que cada
adaptador concreto solo tenga que implementar la llamada cruda al SDK
(``_generate``):

    1. Caché e idempotencia (get)          → core.ai.observability.cache
    2. Redacción de secretos antes de enviar → core.ai.safety
    3. Cronometrado de latencia
    4. Registro de consumo (tokens/costo)   → core.ai.observability.usage_tracker
    5. Caché (set)

Un adaptador concreto define ``provider_name``, ``model_name`` e implementa
``_generate(prompt) -> (text, TokenUsage, FinishReason)``.
"""

import logging
from abc import abstractmethod
from time import perf_counter
from typing import Iterator, Tuple

from django.conf import settings

from ...domain.genai.interfaces import IChatModel
from ...domain.genai.schemas import Completion, FinishReason, Prompt, TokenUsage
from ...observability.cache import get_cached, set_cached
from ...observability.usage_tracker import record_usage
from ...safety import redact_prompt

logger = logging.getLogger('app.ai')


class BaseChatModel(IChatModel):
    """Plantilla de flujo para adaptadores de chat. No usar directamente."""

    provider_name: str = 'base'
    model_name: str = ''

    # ── API pública (template method) ──────────────────────────────────────────

    def complete(self, prompt: Prompt) -> Completion:
        cached = get_cached(prompt, self.model_name)
        if cached is not None:
            return cached

        outgoing = redact_prompt(prompt) if getattr(settings, 'AI_REDACT_PROMPTS', True) else prompt

        start = perf_counter()
        text, usage, finish = self._generate(outgoing)
        latency_ms = int((perf_counter() - start) * 1000)

        completion = Completion(
            text=text,
            model=self.model_name,
            provider=self.provider_name,
            usage=usage,
            finish_reason=finish,
            latency_ms=latency_ms,
        )

        record_usage(
            provider=self.provider_name,
            model=self.model_name,
            usage=usage,
            latency_ms=latency_ms,
            feature=prompt.options.metadata.get('feature', '-'),
        )
        set_cached(prompt, self.model_name, completion)
        return completion

    def stream(self, prompt: Prompt) -> Iterator[str]:
        """
        Streaming por defecto: genera todo y emite una sola pieza.

        Los adaptadores con streaming nativo (p. ej. Anthropic) sobreescriben
        este método para emitir token a token.
        """
        yield self.complete(prompt).text

    # ── A implementar por cada proveedor ───────────────────────────────────────

    @abstractmethod
    def _generate(self, prompt: Prompt) -> Tuple[str, TokenUsage, FinishReason]:
        """Llamada cruda al proveedor. Devuelve (texto, uso, motivo de fin)."""
        ...
