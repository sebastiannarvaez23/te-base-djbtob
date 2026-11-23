from abc import ABC, abstractmethod
from typing import Optional

from platform.features.configuration.assistant.assistant.domain.schemas import (
    AssistantSettingsPersistSchema,
    AssistantUsageSchema,
)


class IAssistantSettingsRepository(ABC):

    @abstractmethod
    def get(self) -> Optional[AssistantSettingsPersistSchema]:
        ...

    @abstractmethod
    def save(self, data: AssistantSettingsPersistSchema) -> AssistantSettingsPersistSchema:
        ...


class IRuntimeHealthProbe(ABC):

    @abstractmethod
    def probe(self, provider: str) -> str:
        ...


class IAssistantUsageReader(ABC):

    @abstractmethod
    def collect_24h(self) -> AssistantUsageSchema:
        ...
