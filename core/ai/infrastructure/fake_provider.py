"""Backward-compatible re-export — prefer ``core.ai.infrastructure.genai``."""

from .genai.fake_provider import FakeChatModel, FakeDocumentExtractor, FakeEmbedder

__all__ = ['FakeChatModel', 'FakeEmbedder', 'FakeDocumentExtractor']
