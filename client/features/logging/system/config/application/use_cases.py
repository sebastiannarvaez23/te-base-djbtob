from typing import Optional

from client.features.logging.system.config.domain.interfaces import ILogConfigRepository
from client.features.logging.system.config.domain.schemas import LogRetentionConfigSchema, LogRetentionConfigUpdateSchema
from core.query.core import PaginatedQuery, PaginatedResult
from core.trace import trace_layer


class GetLogConfigUseCase:
    def __init__(self, repository: ILogConfigRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, log_type: str) -> Optional[LogRetentionConfigSchema]:
        return self.repository.get_config(log_type)


class GetAllLogConfigsUseCase:
    def __init__(self, repository: ILogConfigRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, query: PaginatedQuery) -> PaginatedResult:
        return self.repository.get_all_configs(query)


class UpdateLogConfigUseCase:
    def __init__(self, repository: ILogConfigRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, log_type: str, data: LogRetentionConfigUpdateSchema) -> LogRetentionConfigSchema:
        current = self.repository.get_config(log_type)

        updated = LogRetentionConfigSchema(
            log_type=log_type,
            enabled=data.enabled if data.enabled is not None else (current.enabled if current else True),
            retention_days=data.retention_days if data.retention_days is not None else (current.retention_days if current else 90),
            archive_enabled=data.archive_enabled if data.archive_enabled is not None else (current.archive_enabled if current else False),
            archive_after_days=data.archive_after_days if data.archive_after_days is not None else (current.archive_after_days if current else 60),
            max_records=data.max_records if data.max_records is not None else (current.max_records if current else None),
            cleanup_frequency=data.cleanup_frequency if data.cleanup_frequency is not None else (current.cleanup_frequency if current else 'daily'),
        )

        return self.repository.update_config(log_type, updated)
