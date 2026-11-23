"""Backward-compatible re-export — prefer ``core.ai.infrastructure.genai``."""

from .genai.local_provider import LocalChatModel

__all__ = ['LocalChatModel']
