"""Adaptadores de health / usage para settings del assistant."""

from core.ai.health import RuntimeHealthProbe
from platform.features.configuration.assistant.assistant.domain.interfaces import (
    IAssistantUsageReader,
    IRuntimeHealthProbe,
)
from platform.features.configuration.assistant.assistant.domain.schemas import AssistantUsageSchema
from platform.features.configuration.assistant.assistant.infrastructure.usage import collect_usage_24h


class CoreRuntimeHealthProbe(IRuntimeHealthProbe):
    def __init__(self, probe: RuntimeHealthProbe | None = None):
        self._probe = probe or RuntimeHealthProbe()

    def probe(self, provider: str) -> str:
        return self._probe.probe(provider)


class TenantAssistantUsageReader(IAssistantUsageReader):
    def collect_24h(self) -> AssistantUsageSchema:
        return collect_usage_24h()


class NullAssistantUsageReader(IAssistantUsageReader):
    """Sin barrido multi-tenant (PATCH / tests)."""

    def collect_24h(self) -> AssistantUsageSchema:
        return AssistantUsageSchema()


class StaticRuntimeHealthProbe(IRuntimeHealthProbe):
    def __init__(self, status: str = 'unknown'):
        self._status = status

    def probe(self, provider: str) -> str:
        return self._status
