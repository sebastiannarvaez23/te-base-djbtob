from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.ai.model_layer.catalog import AI_CAPABILITIES, AI_CHAT_PROVIDERS
from core.ai.model_layer.schemas import ModelRouteDecision, ModelRoutingTable


class ModelRouteAdminSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    capability: str
    provider: str
    model_id: str = ''
    credential_source: str = 'platform'
    fallbacks: list[str] = Field(default_factory=list)
    max_tokens: int = 1024
    timeout_s: float = 60.0
    max_cost_usd: Optional[Decimal] = None
    max_latency_ms: Optional[int] = None
    runtime_health: str = 'unknown'

    @field_validator('capability')
    @classmethod
    def capability_ok(cls, value: str) -> str:
        cap = (value or '').lower().strip()
        if cap not in AI_CAPABILITIES:
            raise ValueError(f'Unknown capability: {value}')
        return cap

    @field_validator('provider')
    @classmethod
    def provider_ok(cls, value: str) -> str:
        name = (value or 'fake').lower()
        if name not in AI_CHAT_PROVIDERS:
            raise ValueError(f'Invalid provider: {value}')
        return name


class ModelRoutingAdminSchema(BaseModel):
    id: Optional[UUID] = None
    routes: list[ModelRouteAdminSchema] = Field(default_factory=list)
    hourly_budget_usd: Optional[Decimal] = None
    spent_usd_window: Decimal = Decimal('0')
    updated_at: Optional[datetime] = None


def table_to_admin_routes(
    table: ModelRoutingTable,
    *,
    health_by_provider: dict[str, str] | None = None,
) -> list[ModelRouteAdminSchema]:
    health_by_provider = health_by_provider or {}
    rows: list[ModelRouteAdminSchema] = []
    for cap in AI_CAPABILITIES:
        route = table.routes.get(cap) or ModelRouteDecision(provider='fake')
        rows.append(ModelRouteAdminSchema(
            capability=cap,
            provider=route.provider,
            model_id=route.model_id,
            credential_source=route.credential_source,
            fallbacks=list(route.fallbacks),
            max_tokens=route.max_tokens,
            timeout_s=route.timeout_s,
            max_cost_usd=route.max_cost_usd,
            max_latency_ms=route.max_latency_ms,
            runtime_health=health_by_provider.get(route.provider, 'unknown'),
        ))
    return rows


def admin_routes_to_table(
    routes: list[dict],
    *,
    hourly_budget_usd: Optional[Decimal] = None,
) -> ModelRoutingTable:
    mapped: dict[str, ModelRouteDecision] = {}
    for item in routes or []:
        cap = (item.get('capability') or '').lower().strip()
        if cap not in AI_CAPABILITIES:
            continue
        mapped[cap] = ModelRouteDecision.model_validate({
            'provider': item.get('provider') or 'fake',
            'model_id': item.get('model_id') or '',
            'credential_source': item.get('credential_source') or 'platform',
            'fallbacks': item.get('fallbacks') or [],
            'max_tokens': item.get('max_tokens') or 1024,
            'timeout_s': item.get('timeout_s') or 60.0,
            'max_cost_usd': item.get('max_cost_usd'),
            'max_latency_ms': item.get('max_latency_ms'),
        })
    return ModelRoutingTable(routes=mapped, hourly_budget_usd=hourly_budget_usd)
