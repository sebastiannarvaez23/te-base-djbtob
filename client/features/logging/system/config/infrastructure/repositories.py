from typing import Optional

from client.features.logging.system.config.domain.interfaces import ILogConfigRepository
from client.features.logging.system.config.domain.schemas import LogRetentionConfigSchema
from core.query.core import PaginatedQuery, PaginatedResult


class DjangoLogConfigRepository(ILogConfigRepository):

    def get_config(self, log_type: str) -> Optional[LogRetentionConfigSchema]:
        from client.features.logging.system.config.models import LogConfiguration
        try:
            config = LogConfiguration.objects.get(log_type=log_type)
            return LogRetentionConfigSchema.model_validate(config)
        except LogConfiguration.DoesNotExist:
            return None

    def update_config(self, log_type: str, data: LogRetentionConfigSchema) -> LogRetentionConfigSchema:
        from client.features.logging.system.config.models import LogConfiguration
        config, _ = LogConfiguration.objects.update_or_create(
            log_type=log_type,
            defaults={
                'enabled': data.enabled,
                'retention_days': data.retention_days,
                'archive_enabled': data.archive_enabled,
                'archive_after_days': data.archive_after_days,
                'max_records': data.max_records,
                'cleanup_frequency': data.cleanup_frequency,
            },
        )
        return LogRetentionConfigSchema.model_validate(config)

    def get_all_configs(self, query: PaginatedQuery) -> PaginatedResult:
        from client.features.logging.system.config.models import LogConfiguration

        qs = LogConfiguration.objects.all().order_by('log_type')
        f = query.filters
        if 'log_type' in f:
            qs = qs.filter(log_type=f['log_type'])
        if 'enabled' in f:
            qs = qs.filter(enabled=bool(f['enabled']))

        if query.unpaginated:
            items = [LogRetentionConfigSchema.model_validate(c) for c in qs]
            return PaginatedResult(
                items=items, total=len(items), page=0, page_size=0, total_pages=1,
            )

        total = qs.count()
        items = [
            LogRetentionConfigSchema.model_validate(c)
            for c in qs[query.offset: query.offset + query.limit]
        ]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items, total=total, page=query.page,
            page_size=query.page_size, total_pages=total_pages,
        )
