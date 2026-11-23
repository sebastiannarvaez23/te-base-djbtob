"""
core/ai
───────
Módulo transversal de Inteligencia Artificial de la plataforma.

Particionado por capacidad:
  - ``domain/genai`` + ``infrastructure/genai``       — cubos 1–2 (chat/embed/docs)
  - ``domain/optimization`` + ``infrastructure/optimization`` — cubo 4 (OR)
  - ``domain/predictive`` + ``infrastructure/predictive``     — cubo 3 (ML)

La lógica de negocio depende de los puertos, nunca del runtime/solver/artefacto.
"""

from .config import (
    get_anomaly_detector,
    get_batch_grouper,
    get_chat_model,
    get_demand_forecaster,
    get_document_extractor,
    get_embedder,
    get_picking_router,
    is_ai_enabled,
    is_ml_enabled,
    is_or_enabled,
)
from .assistant_policy import AssistantRuntimePolicy, default_assistant_policy
from .model_layer import resolve_chat_model
from .domain.genai.interfaces import IChatModel, IDocumentExtractor, IEmbedder
from .domain.genai.schemas import (
    ChatOptions,
    Completion,
    EmbeddingResult,
    ExtractionResult,
    Message,
    MessageRole,
    Prompt,
    TokenUsage,
)
from .domain.optimization.interfaces import IBatchGrouper, IPickingRouter
from .domain.predictive.interfaces import IAnomalyDetector, IDemandForecaster

__all__ = [
    # Factory / config
    'get_chat_model',
    'resolve_chat_model',
    'get_embedder',
    'get_document_extractor',
    'get_picking_router',
    'get_batch_grouper',
    'get_demand_forecaster',
    'get_anomaly_detector',
    'is_ai_enabled',
    'is_or_enabled',
    'is_ml_enabled',
    'AssistantRuntimePolicy',
    'default_assistant_policy',
    # GenAI ports / schemas
    'IChatModel',
    'IEmbedder',
    'IDocumentExtractor',
    'ChatOptions',
    'Completion',
    'EmbeddingResult',
    'ExtractionResult',
    'Message',
    'MessageRole',
    'Prompt',
    'TokenUsage',
    # OR / Predictive ports
    'IPickingRouter',
    'IBatchGrouper',
    'IDemandForecaster',
    'IAnomalyDetector',
]
