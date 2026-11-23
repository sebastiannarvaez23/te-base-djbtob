"""Backward-compatible re-export — prefer ``core.ai.domain.genai``."""

from .genai.interfaces import IChatModel, IDocumentExtractor, IEmbedder

__all__ = ['IChatModel', 'IEmbedder', 'IDocumentExtractor']
