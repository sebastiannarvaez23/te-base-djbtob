"""Backward-compatible re-export — prefer ``core.ai.infrastructure.genai``."""

from .genai.anthropic_provider import AnthropicChatModel

__all__ = ['AnthropicChatModel']
