"""
core/ai/observability/usage_tracker.py
───────────────────────────────────────
Registro de consumo de IA por llamada: tokens, costo estimado, latencia,
modelo, proveedor y tenant. Es la base para FinOps de IA (Fase 7) y para la
auditoría de uso por empresa exigida en un B2B.

Diseño best-effort: registrar el uso NUNCA debe romper el flujo principal
(igual que el logging de auditoría del proyecto). Todo va envuelto en try/except.

Hoy emite a un logger dedicado ('app.ai'). Cuando la Fase 7 lo requiera, este
mismo punto puede persistir a base de datos o emitir métricas sin cambiar a los
llamadores.
"""

import logging

from django.conf import settings
from django.db import connection

from ..domain.schemas import TokenUsage

logger = logging.getLogger('app.ai')


def _current_tenant() -> str:
    """Schema del tenant activo (django-tenants). 'public' o '-' si no aplica."""
    try:
        return getattr(connection, 'schema_name', '-') or '-'
    except Exception:
        return '-'


def _estimate_cost_usd(provider: str, model: str, usage: TokenUsage) -> float:
    """
    Costo estimado en USD a partir de una tabla de precios por millón de tokens.

    Es una estimación para observabilidad, no facturación. La tabla se configura
    en ``settings.AI_PRICING`` como:
        {'<provider>:<model>': {'input': <usd_por_millon>, 'output': <usd_por_millon>}}
    Si no hay precio configurado, retorna 0.0 (desconocido).
    """
    try:
        pricing = getattr(settings, 'AI_PRICING', {}) or {}
        entry = pricing.get(f'{provider}:{model}') or pricing.get(model)
        if not entry:
            return 0.0
        return round(
            usage.input_tokens / 1_000_000 * entry.get('input', 0.0)
            + usage.output_tokens / 1_000_000 * entry.get('output', 0.0),
            6,
        )
    except Exception:
        return 0.0


def record_usage(
    *,
    provider: str,
    model: str,
    usage: TokenUsage,
    latency_ms: int,
    feature: str = '-',
    degraded: bool = False,
    capability: str = 'genai',
) -> None:
    """
    Registra el uso de una llamada de IA. Best-effort: silencia cualquier error.

    Args:
        provider:   Nombre del proveedor ('anthropic', 'openai', 'fake'…).
        model:      Identificador del modelo usado.
        usage:      Tokens de entrada/salida (GenAI); puede ser cero en OR/ML.
        latency_ms: Latencia observada de la llamada.
        feature:    Nombre lógico de la feature que consumió IA (para agrupar).
        degraded:   True si la llamada terminó en fallback (proveedor caído).
        capability: ``genai`` | ``optimization`` | ``predictive`` (AiCapability).
    """
    try:
        from ..domain.common import AiCapability
        try:
            capability = AiCapability(capability).value
        except ValueError:
            capability = AiCapability.GENAI.value
        cost = _estimate_cost_usd(provider, model, usage)
        logger.info(
            'ai_usage',
            extra={
                'ai_provider': provider,
                'ai_model': model,
                'ai_tenant': _current_tenant(),
                'ai_feature': feature,
                'ai_capability': capability,
                'ai_input_tokens': usage.input_tokens,
                'ai_output_tokens': usage.output_tokens,
                'ai_total_tokens': usage.total_tokens,
                'ai_cost_usd': cost,
                'ai_latency_ms': latency_ms,
                'ai_degraded': degraded,
            },
        )
        if cost > 0:
            try:
                from core.ai.model_layer.budget import BudgetGuard
                BudgetGuard().record_cost(cost)
            except Exception:
                pass
    except Exception:  # nunca interrumpir el flujo por telemetría
        pass
