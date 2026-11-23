"""
core/ai/resilience.py
──────────────────────
Degradación con elegancia (fallback) para llamadas de IA.

La IA es no-determinista, con latencia variable y dependiente de un proveedor
externo. Ninguna feature del WMS debe romperse porque el proveedor falle o
tarde. Este módulo ofrece envoltorios que convierten un fallo en una respuesta
degradada (best-effort), igual que el sistema de incidencias del proyecto.

Uso típico en un use case (Fase 1):

    from core.ai.resilience import complete_or

    completion = complete_or(
        self.model, prompt,
        fallback='Resumen no disponible por ahora.',
        feature='dashboard.day_summary',
    )
    # completion.degraded == True si hubo fallback
"""

import logging
from typing import Iterator

from .domain.schemas import Completion, FinishReason, Prompt, TokenUsage
from .observability.usage_tracker import record_usage

logger = logging.getLogger('app.ai')


def complete_or(model, prompt: Prompt, *, fallback: str, feature: str = '-') -> Completion:
    """
    Ejecuta ``model.complete(prompt)`` y, si falla por cualquier motivo,
    devuelve una ``Completion`` degradada con el texto ``fallback``.

    Registra el fallo (best-effort) para observabilidad. No relanza.
    """
    try:
        return model.complete(prompt)
    except Exception as exc:
        logger.warning(f'AI complete failed [{feature}]: {exc}; using fallback')
        try:
            record_usage(
                provider=getattr(model, 'provider_name', 'unknown'),
                model=getattr(model, 'model_name', '-'),
                usage=TokenUsage(),
                latency_ms=0,
                feature=feature,
                degraded=True,
            )
        except Exception:
            pass
        return Completion(
            text=fallback,
            provider=getattr(model, 'provider_name', 'unknown'),
            finish_reason=FinishReason.ERROR,
            degraded=True,
        )


def stream_accumulate_or(
    model,
    prompt: Prompt,
    *,
    fallback: str,
    feature: str = '-',
) -> Iterator[dict]:
    """
    Intenta ``model.stream(prompt)`` y yield ``{'delta': str, 'degraded': bool}``.

    Si el stream falla, cae a ``complete_or`` y emite un único delta con el
    texto completo (posible ``degraded=True``).
    """
    try:
        emitted = False
        for chunk in model.stream(prompt):
            if not chunk:
                continue
            emitted = True
            yield {'delta': chunk, 'degraded': False}
        if emitted:
            return
    except Exception as exc:
        logger.warning(f'AI stream failed [{feature}]: {exc}; falling back to complete')

    completion = complete_or(model, prompt, fallback=fallback, feature=feature)
    if completion.text:
        yield {'delta': completion.text, 'degraded': bool(completion.degraded)}


def solve_or(router, request, *, feature: str = '-'):
    """
    Ejecuta ``router.route(request)`` con degradación best-effort.

    Si falla, retorna un resultado vacío con ``degraded=True`` (mismo shape).
    """
    try:
        return router.route(request)
    except Exception as exc:
        logger.warning(f'OR route failed [{feature}]: {exc}; using empty result')
        from .domain.optimization.schemas import PickingRouteResult
        from .observability.usage_tracker import record_usage
        from .domain.genai.schemas import TokenUsage

        try:
            record_usage(
                provider=getattr(router, 'provider_name', 'unknown'),
                model='-',
                usage=TokenUsage(),
                latency_ms=0,
                feature=feature,
                degraded=True,
                capability='optimization',
            )
        except Exception:
            pass
        return PickingRouteResult(
            provider=getattr(router, 'provider_name', 'unknown'),
            degraded=True,
        )


def predict_or(forecaster, request, *, feature: str = '-'):
    """Ejecuta ``forecaster.forecast(request)`` con degradación best-effort."""
    try:
        return forecaster.forecast(request)
    except Exception as exc:
        logger.warning(f'ML forecast failed [{feature}]: {exc}; using empty result')
        from .domain.predictive.schemas import DemandForecastResult
        from .observability.usage_tracker import record_usage
        from .domain.genai.schemas import TokenUsage

        try:
            record_usage(
                provider=getattr(forecaster, 'provider_name', 'unknown'),
                model=getattr(forecaster, 'model_version', '-'),
                usage=TokenUsage(),
                latency_ms=0,
                feature=feature,
                degraded=True,
                capability='predictive',
            )
        except Exception:
            pass
        return DemandForecastResult(
            sku_id=getattr(request, 'sku_id', ''),
            provider=getattr(forecaster, 'provider_name', 'unknown'),
            degraded=True,
        )
