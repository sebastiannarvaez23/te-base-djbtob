"""Contratos Pydantic de la capa de modelos."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .catalog import AI_CAPABILITIES, AI_CHAT_PROVIDERS


class ModelRouteDecision(BaseModel):
    """Decisión de routing para una capacidad (chat, forecast, …)."""

    model_config = ConfigDict(protected_namespaces=())

    provider: str = 'fake'
    model_id: str = ''
    credential_source: str = 'platform'  # platform | tenant_byok
    fallbacks: list[str] = Field(default_factory=list)
    max_tokens: int = Field(default=1024, ge=1, le=128_000)
    timeout_s: float = Field(default=60.0, ge=1.0, le=600.0)
    max_cost_usd: Optional[Decimal] = None
    max_latency_ms: Optional[int] = Field(default=None, ge=100, le=600_000)

    @field_validator('provider')
    @classmethod
    def provider_ok(cls, value: str) -> str:
        name = (value or 'fake').lower()
        if name not in AI_CHAT_PROVIDERS:
            raise ValueError(f'Invalid provider: {value}')
        return name

    @field_validator('fallbacks')
    @classmethod
    def fallbacks_ok(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value or []:
            name = (item or '').lower().strip()
            if name and name in AI_CHAT_PROVIDERS and name not in cleaned:
                cleaned.append(name)
        return cleaned

    @field_validator('credential_source')
    @classmethod
    def credential_ok(cls, value: str) -> str:
        src = (value or 'platform').lower()
        if src not in ('platform', 'tenant_byok'):
            raise ValueError('credential_source must be platform|tenant_byok')
        return src

    def candidate_providers(self) -> list[str]:
        ordered = [self.provider]
        for name in self.fallbacks:
            if name not in ordered:
                ordered.append(name)
        return ordered


class ModelRoutingTable(BaseModel):
    """Tabla completa capacidad → ruta (singleton de plataforma)."""

    routes: dict[str, ModelRouteDecision] = Field(default_factory=dict)
    hourly_budget_usd: Optional[Decimal] = None

    @field_validator('routes')
    @classmethod
    def routes_keys(cls, value: dict) -> dict:
        out: dict[str, ModelRouteDecision] = {}
        for key, route in (value or {}).items():
            cap = (key or '').strip().lower()
            if cap not in AI_CAPABILITIES:
                continue
            if isinstance(route, ModelRouteDecision):
                out[cap] = route
            elif isinstance(route, dict):
                out[cap] = ModelRouteDecision.model_validate(route)
        return out
