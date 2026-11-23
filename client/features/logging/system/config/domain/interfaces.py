from abc import ABC, abstractmethod
from typing import Optional

from client.features.logging.system.config.domain.schemas import LogRetentionConfigSchema
from core.query.core import PaginatedQuery, PaginatedResult


class ILogConfigRepository(ABC):
    """Port: gestiona la configuración de retención y habilitación de logs."""

    @abstractmethod
    def get_config(self, log_type: str) -> Optional[LogRetentionConfigSchema]:
        ...

    @abstractmethod
    def update_config(self, log_type: str, data: LogRetentionConfigSchema) -> LogRetentionConfigSchema:
        ...

    @abstractmethod
    def get_all_configs(self, query: PaginatedQuery) -> PaginatedResult:
        ...
