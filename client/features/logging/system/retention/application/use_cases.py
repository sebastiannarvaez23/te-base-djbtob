import logging

from client.features.logging.system.config.domain.interfaces import ILogConfigRepository
from client.features.logging.system.retention.domain.interfaces import ILogRetentionStrategy
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class ExecuteRetentionUseCase:
    """Ejecuta la limpieza y archivado de logs según la configuración de cada tipo."""

    def __init__(
        self,
        config_repo: ILogConfigRepository,
        db_strategy: ILogRetentionStrategy,
        file_strategy: ILogRetentionStrategy,
        tenant_strategy: ILogRetentionStrategy = None,
    ):
        self.config_repo = config_repo
        self.db_strategy = db_strategy
        self.file_strategy = file_strategy
        self.tenant_strategy = tenant_strategy

    # Tipos de log que persisten en DB vs archivos vs carpeta por empresa
    DB_LOG_TYPES = {'audit', 'operations', 'integration', 'security'}
    FILE_LOG_TYPES = {'errors', 'performance', 'system'}
    TENANT_LOG_TYPES = {'tenant'}

    @trace_layer('application')
    def execute_all(self) -> dict[str, int]:
        """Ejecuta retención para todos los tipos configurados. Retorna {log_type: registros_eliminados}."""
        configs = self.config_repo.get_all_configs()
        results = {}

        for config in configs:
            if not config.enabled:
                continue
            results[config.log_type] = self._process_type(config.log_type, config)

        return results

    @trace_layer('application')
    def execute_for_type(self, log_type: str) -> int:
        """Ejecuta retención para un tipo específico."""
        config = self.config_repo.get_config(log_type)
        if not config or not config.enabled:
            return 0
        return self._process_type(log_type, config)

    def _process_type(self, log_type: str, config) -> int:
        strategy = self._select_strategy(log_type)
        total = 0

        try:
            if config.archive_enabled:
                archived = strategy.execute_archive(log_type, config)
                total += archived
                logger.info('RETENTION_ARCHIVE log_type=%s archived=%d', log_type, archived)

            deleted = strategy.execute_cleanup(log_type, config)
            total += deleted
            logger.info('RETENTION_CLEANUP log_type=%s deleted=%d', log_type, deleted)
        except Exception as exc:
            logger.error('RETENTION_ERROR log_type=%s error=%s', log_type, str(exc))

        return total

    def _select_strategy(self, log_type: str) -> ILogRetentionStrategy:
        if log_type in self.DB_LOG_TYPES:
            return self.db_strategy
        if log_type in self.TENANT_LOG_TYPES and self.tenant_strategy is not None:
            return self.tenant_strategy
        return self.file_strategy
