"""
core/ai/config.py
─────────────────
Factory de proveedores de IA por capacidad (GenAI / OR / Predictive).

    from core.ai import get_chat_model, get_picking_router, get_demand_forecaster
"""

from django.conf import settings

from core.errors import AppErrorCode, ServerException

from .domain.genai.interfaces import IChatModel, IDocumentExtractor, IEmbedder
from .domain.optimization.interfaces import IBatchGrouper, IPickingRouter
from .domain.predictive.interfaces import IAnomalyDetector, IDemandForecaster


def is_ai_enabled() -> bool:
    """True si GenAI está habilitada globalmente (kill-switch de producto)."""
    return getattr(settings, 'AI_ENABLED', True)


def is_or_enabled() -> bool:
    """True si optimización (OR) está habilitada."""
    return getattr(settings, 'OR_ENABLED', True)


def is_ml_enabled() -> bool:
    """True si ML predictivo está habilitado."""
    return getattr(settings, 'ML_ENABLED', True)


def _provider_name(override: str | None = None) -> str:
    return (override or getattr(settings, 'AI_PROVIDER', 'fake')).lower()


def get_chat_model(
    provider: str | None = None,
    *,
    model_id: str | None = None,
    api_key: str | None = None,
    max_tokens: int | None = None,
    timeout_s: float | None = None,
) -> IChatModel:
    """
    Instancia un ``IChatModel``.

    ``model_id`` / ``api_key`` / límites son opcionales (routing / BYOK).
    """
    name = _provider_name(provider)

    if name != 'fake' and not is_ai_enabled():
        raise ServerException(AppErrorCode.AI_DISABLED)

    if name == 'local':
        from .infrastructure.genai.local_provider import LocalChatModel
        return LocalChatModel(model=model_id)

    if name == 'anthropic':
        from .infrastructure.genai.anthropic_provider import AnthropicChatModel
        return AnthropicChatModel(
            model=model_id,
            api_key=api_key,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

    if name == 'openai':
        from .infrastructure.genai.openai_provider import OpenAIChatModel
        return OpenAIChatModel(
            model=model_id,
            api_key=api_key,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
        )

    from .infrastructure.genai.fake_provider import FakeChatModel
    return FakeChatModel()


def get_embedder(provider: str | None = None) -> IEmbedder:
    """
    Selecciona el adaptador de embeddings.

    Hoy solo ``fake`` está implementado; proveedores desconocidos caen a fake.
    """
    name = (provider or getattr(settings, 'AI_EMBEDDING_PROVIDER', 'fake')).lower()
    if name not in ('fake',):
        # Future: local/openai/etc. Until then, only fake is available.
        name = 'fake'
    from .infrastructure.genai.fake_provider import FakeEmbedder
    return FakeEmbedder()


def get_document_extractor(provider: str | None = None) -> IDocumentExtractor:
    """Document/vision extractor (cubo 2). Only fake stub until Fase 1."""
    name = (provider or getattr(settings, 'AI_DOCUMENT_PROVIDER', 'fake')).lower()
    if name != 'fake' and not is_ai_enabled():
        raise ServerException(AppErrorCode.AI_DISABLED)
    from .infrastructure.genai.fake_provider import FakeDocumentExtractor
    return FakeDocumentExtractor()


def get_picking_router(provider: str | None = None) -> IPickingRouter:
    name = (provider or getattr(settings, 'OR_PROVIDER', 'fake')).lower()
    if name != 'fake' and not is_or_enabled():
        raise ServerException(AppErrorCode.AI_OR_DISABLED)
    from .infrastructure.optimization.fake_provider import FakePickingRouter
    return FakePickingRouter()


def get_batch_grouper(provider: str | None = None) -> IBatchGrouper:
    name = (provider or getattr(settings, 'OR_PROVIDER', 'fake')).lower()
    if name != 'fake' and not is_or_enabled():
        raise ServerException(AppErrorCode.AI_OR_DISABLED)
    from .infrastructure.optimization.fake_provider import FakeBatchGrouper
    return FakeBatchGrouper()


def get_demand_forecaster(provider: str | None = None) -> IDemandForecaster:
    name = (provider or getattr(settings, 'ML_PROVIDER', 'fake')).lower()
    if name != 'fake' and not is_ml_enabled():
        raise ServerException(AppErrorCode.AI_ML_DISABLED)
    from .infrastructure.predictive.fake_provider import FakeDemandForecaster
    return FakeDemandForecaster()


def get_anomaly_detector(provider: str | None = None) -> IAnomalyDetector:
    name = (provider or getattr(settings, 'ML_PROVIDER', 'fake')).lower()
    if name != 'fake' and not is_ml_enabled():
        raise ServerException(AppErrorCode.AI_ML_DISABLED)
    from .infrastructure.predictive.fake_provider import FakeAnomalyDetector
    return FakeAnomalyDetector()
