"""
Capa de modelos: selección, routing, fallbacks y presupuestos.

Uso típico::

    from core.ai.model_layer import resolve_chat_model

    model, route = resolve_chat_model('chat', preferred_provider='local')
"""

from .budget import BudgetGuard
from .catalog import AI_CAPABILITIES, AI_CHAT_PROVIDERS
from .router import ModelRouter, resolve_chat_model
from .schemas import ModelRouteDecision, ModelRoutingTable

__all__ = [
    'AI_CAPABILITIES',
    'AI_CHAT_PROVIDERS',
    'BudgetGuard',
    'ModelRouteDecision',
    'ModelRoutingTable',
    'ModelRouter',
    'resolve_chat_model',
]
