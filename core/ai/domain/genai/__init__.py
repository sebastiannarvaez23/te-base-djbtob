"""GenAI ports and schemas (cubos 1–2)."""

from .interfaces import IChatModel, IDocumentExtractor, IEmbedder
from .schemas import (
    ChatOptions,
    Completion,
    EmbeddingResult,
    ExtractionResult,
    FinishReason,
    Message,
    MessageRole,
    Prompt,
    TokenUsage,
)

__all__ = [
    'IChatModel',
    'IEmbedder',
    'IDocumentExtractor',
    'ChatOptions',
    'Completion',
    'EmbeddingResult',
    'ExtractionResult',
    'FinishReason',
    'Message',
    'MessageRole',
    'Prompt',
    'TokenUsage',
]
