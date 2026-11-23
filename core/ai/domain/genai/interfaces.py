"""
core/ai/domain/genai/interfaces.py
──────────────────────────────────
Puertos GenAI (chat, embeddings, document extraction).
"""

from abc import ABC, abstractmethod
from typing import Iterator, List

from .schemas import Completion, EmbeddingResult, ExtractionResult, Prompt


class IChatModel(ABC):
    """
    Puerto de salida hacia un modelo de lenguaje (LLM) — cubo 1 (GenAI texto).

    Responsabilidades:
    - Generar una respuesta completa a partir de un ``Prompt``.
    - Generar en streaming (token a token) para UX conversacional en tiempo real.
    """

    @abstractmethod
    def complete(self, prompt: Prompt) -> Completion:
        """
        Genera una respuesta completa (bloqueante).

        Registra consumo de tokens/latencia vía observabilidad.
        Lanza ServerException(AI_*) si el proveedor falla (salvo que se use
        con un envoltorio de fallback).
        """
        ...

    @abstractmethod
    def stream(self, prompt: Prompt) -> Iterator[str]:
        """
        Genera la respuesta en fragmentos incrementales (streaming).

        Pensado para emitir vía WebSockets. Cada elemento es un trozo de texto.
        """
        ...


class IEmbedder(ABC):
    """
    Puerto de salida hacia un modelo de embeddings — búsqueda semántica / RAG.
    """

    @abstractmethod
    def embed(self, text: str) -> EmbeddingResult:
        """Genera el vector de embedding de un texto."""
        ...

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Genera embeddings para varios textos en una sola llamada (eficiencia)."""
        ...


class IDocumentExtractor(ABC):
    """
    Puerto de salida para extracción estructurada de documentos — cubo 2
    (GenAI documentos/visión). Ej.: leer una factura/PO en PDF o imagen y
    devolver datos estructurados.
    """

    @abstractmethod
    def extract(self, content: bytes, content_type: str, schema_hint: dict) -> ExtractionResult:
        """
        Extrae datos estructurados de un documento.

        Args:
            content:      Bytes del documento (PDF, PNG, JPG…).
            content_type: MIME type del documento.
            schema_hint:  Descripción del schema esperado (guía al modelo).
        """
        ...
