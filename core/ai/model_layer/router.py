"""Router de modelos: selección + fallbacks + presupuesto."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.conf import settings

from core.ai.domain.genai.interfaces import IChatModel
from core.errors import AppErrorCode, ServerException

from .budget import BudgetGuard
from .catalog import AI_CAPABILITIES
from .schemas import ModelRouteDecision, ModelRoutingTable

logger = logging.getLogger('app.ai')


def default_routing_table() -> ModelRoutingTable:
    """Defaults seguros desde settings (sin fila en BD)."""
    provider = (getattr(settings, 'AI_PROVIDER', 'fake') or 'fake').lower()
    model_id = getattr(settings, 'AI_CHAT_MODEL', '') or ''
    max_tokens = int(getattr(settings, 'AI_MAX_TOKENS', 1024) or 1024)
    timeout_s = float(getattr(settings, 'AI_TIMEOUT_SECONDS', 60.0) or 60.0)
    chat = ModelRouteDecision(
        provider=provider if provider in ('fake', 'local', 'anthropic', 'openai') else 'fake',
        model_id=model_id,
        credential_source='platform',
        fallbacks=['fake'] if provider != 'fake' else [],
        max_tokens=max_tokens,
        timeout_s=timeout_s,
    )
    stub = ModelRouteDecision(provider='fake', model_id='', fallbacks=[])
    routes = {cap: stub for cap in AI_CAPABILITIES}
    routes['chat'] = chat
    raw_budget = getattr(settings, 'AI_HOURLY_BUDGET_USD', None)
    hourly = Decimal(str(raw_budget)) if raw_budget not in (None, '') else None
    return ModelRoutingTable(routes=routes, hourly_budget_usd=hourly)


class ModelRouter:
    """Resuelve ``ModelRouteDecision`` por capacidad (+ preferred provider)."""

    def __init__(self, table: ModelRoutingTable | None = None):
        self.table = table or default_routing_table()

    def resolve(
        self,
        capability: str = 'chat',
        *,
        preferred_provider: str | None = None,
    ) -> ModelRouteDecision:
        cap = (capability or 'chat').lower()
        base = self.table.routes.get(cap) or default_routing_table().routes.get(cap)
        if base is None:
            base = ModelRouteDecision(provider='fake')
        if preferred_provider:
            pref = preferred_provider.lower()
            if pref != base.provider:
                fallbacks = [p for p in base.candidate_providers() if p != pref]
                return base.model_copy(update={
                    'provider': pref,
                    'fallbacks': fallbacks,
                })
        return base


def resolve_chat_model(
    capability: str = 'chat',
    *,
    preferred_provider: str | None = None,
    table: ModelRoutingTable | None = None,
    api_key: str | None = None,
    api_key_provider: str | None = None,
) -> tuple[IChatModel, ModelRouteDecision]:
    """
    Instancia ``IChatModel`` según routing + fallbacks.

    ``api_key`` is only passed to ``api_key_provider`` (BYOK scope). Fallbacks
    use platform credentials. Comprueba presupuesto antes del primer intento.
    """
    from core.ai.config import get_chat_model

    router = ModelRouter(table)
    route = router.resolve(capability, preferred_provider=preferred_provider)
    BudgetGuard(hourly_budget_usd=table.hourly_budget_usd if table else None).assert_allowed(route)

    key_provider = (api_key_provider or '').lower().strip() or None
    last_exc: Exception | None = None
    for provider in route.candidate_providers():
        try:
            scoped_key = api_key if (api_key and key_provider == provider) else None
            model = get_chat_model(
                provider,
                model_id=route.model_id or None,
                api_key=scoped_key,
                max_tokens=route.max_tokens,
                timeout_s=route.timeout_s,
            )
            cred_source = 'tenant_byok' if scoped_key else route.credential_source
            return model, route.model_copy(update={
                'provider': provider,
                'credential_source': cred_source,
            })
        except ServerException as exc:
            last_exc = exc
            logger.info('chat model provider %s unavailable: %s', provider, exc)
            continue
        except Exception as exc:
            last_exc = exc
            logger.info('chat model provider %s failed: %s', provider, exc)
            continue

    if isinstance(last_exc, ServerException):
        raise last_exc
    raise ServerException(
        AppErrorCode.AI_PROVIDER_UNAVAILABLE,
        override_detail='No chat model provider could be resolved.',
    )
