from abc import ABC, abstractmethod

from client.features.logging.system.config.domain.schemas import LogRetentionConfigSchema


class ILogRetentionStrategy(ABC):
    """Port: ejecuta la limpieza o archivado de logs según configuración."""

    @abstractmethod
    def execute_cleanup(self, log_type: str, config: LogRetentionConfigSchema) -> int:
        """Elimina registros que exceden la retención. Retorna cantidad eliminada."""
        ...

    @abstractmethod
    def execute_archive(self, log_type: str, config: LogRetentionConfigSchema) -> int:
        """Archiva registros antiguos. Retorna cantidad archivada."""
        ...
