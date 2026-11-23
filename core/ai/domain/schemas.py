"""Backward-compatible re-export — prefer ``core.ai.domain.genai``."""

from .genai.schemas import (
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
