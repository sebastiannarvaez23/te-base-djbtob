"""
core/ai/infrastructure/fake_provider.py
──────────────────────────────────────────
Adaptadores *fake* deterministas.

Doble propósito:
  1. **Tests**: permiten ejercitar use cases de IA sin red (patrón en memoria).
  2. **Default seguro**: ``AI_PROVIDER='fake'`` recién clonado.

Para el copiloto (system prompt con tools), emite JSON del protocolo
``action=tool|final`` en lugar de eco crudo, para no confundir con un SLM.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from ...domain.genai.interfaces import IDocumentExtractor, IEmbedder
from ...domain.genai.schemas import (
    EmbeddingResult,
    ExtractionResult,
    FinishReason,
    MessageRole,
    Prompt,
    TokenUsage,
)
from .base import BaseChatModel


class FakeChatModel(BaseChatModel):
    """IChatModel determinista para tests y default sin runtime."""

    provider_name = 'fake'

    def __init__(self, model: str = 'fake-1', canned_response: str | None = None):
        self.model_name = model
        self._canned = canned_response

    def _generate(self, prompt: Prompt) -> Tuple[str, TokenUsage, FinishReason]:
        if self._canned is not None:
            text = self._canned
        else:
            text = self._default_text(prompt)

        input_len = sum(len(m.content) for m in prompt.messages) + len(prompt.system or '')
        usage = TokenUsage(
            input_tokens=max(1, input_len // 4),
            output_tokens=max(1, len(text) // 4),
        )
        return text, usage, FinishReason.STOP

    def _default_text(self, prompt: Prompt) -> str:
        last_user = next(
            (m.content for m in reversed(prompt.messages) if m.role == MessageRole.USER),
            '',
        )
        system = prompt.system or ''

        # Protocolo del assistant / agente (JSON tool|final).
        if 'Available tools' in system or 'action' in system and 'final' in system:
            return self._agent_protocol_reply(last_user)

        # Compat tests / uso genérico: eco etiquetado.
        return f'[fake:{self.model_name}] {last_user}'.strip()

    def _agent_protocol_reply(self, last_user: str) -> str:
        lower = (last_user or '').lower()

        if last_user.startswith('Tool result'):
            # Tras una tool: respuesta final corta (datos reales ya vinieron en el tool).
            return json.dumps({
                'action': 'final',
                'text': (
                    'Done: I queried WMS data (fake mode, no SLM). '
                    'For natural-language answers with the local model, '
                    'set AI_PROVIDER=local and start the Ollama runtime.'
                ),
            }, ensure_ascii=False)

        greetings = ('hola', 'buenas', 'hello', 'hey', 'qué tal', 'que tal')
        if any(g in lower for g in greetings):
            return json.dumps({
                'action': 'final',
                'text': (
                    'Hello! I am the assistant. '
                    'Running in fake mode right now; for the native SLM set '
                    'AI_PROVIDER=local.'
                ),
            }, ensure_ascii=False)

        return json.dumps({
            'action': 'final',
            'text': 'I do not have tools for that yet.',
        }, ensure_ascii=False)


class FakeEmbedder(IEmbedder):
    """IEmbedder determinista: vector pequeño derivado del hash del texto."""

    provider_name = 'fake'

    def __init__(self, model: str = 'fake-embed-1', dim: int = 8):
        self.model_name = model
        self._dim = dim

    def _vector(self, text: str) -> List[float]:
        h = abs(hash(text))
        return [((h >> (i * 4)) & 0xF) / 15.0 for i in range(self._dim)]

    def embed(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vector=self._vector(text),
            model=self.model_name,
            provider=self.provider_name,
            usage=TokenUsage(input_tokens=max(1, len(text) // 4)),
        )

    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        return [self.embed(t) for t in texts]


class FakeDocumentExtractor(IDocumentExtractor):
    """Stub extractor: returns empty structured data (Fase 1 will add real OCR)."""

    provider_name = 'fake'

    def __init__(self, model: str = 'fake-extract-1'):
        self.model_name = model

    def extract(self, content: bytes, content_type: str, schema_hint: dict) -> ExtractionResult:
        return ExtractionResult(
            data={
                'content_type': content_type,
                'bytes': len(content or b''),
                'schema_keys': sorted((schema_hint or {}).keys()),
            },
            model=self.model_name,
            provider=self.provider_name,
            usage=TokenUsage(input_tokens=max(1, len(content or b'') // 4)),
            confidence=0.0,
            degraded=True,
        )
