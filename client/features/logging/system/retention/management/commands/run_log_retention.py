"""
Management command para ejecutar la retención de logs.

Uso:
    python manage.py run_log_retention              # todos los tipos
    python manage.py run_log_retention --type audit  # solo auditoría
    python manage.py run_log_retention --type security --type audit
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from client.features.logging.system.config.domain.schemas import LogRetentionConfigSchema
from client.features.logging.system.config.infrastructure.repositories import DjangoLogConfigRepository
from client.features.logging.system.retention.application.use_cases import ExecuteRetentionUseCase
from client.features.logging.system.retention.infrastructure.strategies import (
    DatabaseRetentionStrategy,
    FileRetentionStrategy,
    TenantFileRetentionStrategy,
)


class Command(BaseCommand):
    help = 'Ejecuta la retención (limpieza y archivado) de logs según la configuración.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            action='append',
            dest='log_types',
            help='Tipo(s) de log a procesar. Si no se especifica, procesa todos.',
        )

    def handle(self, *args, **options):
        config_repo = DjangoLogConfigRepository()
        self._ensure_tenant_config(config_repo)

        use_case = ExecuteRetentionUseCase(
            config_repo=config_repo,
            db_strategy=DatabaseRetentionStrategy(),
            file_strategy=FileRetentionStrategy(),
            tenant_strategy=TenantFileRetentionStrategy(),
        )

        log_types = options.get('log_types')

        if log_types:
            for log_type in log_types:
                count = use_case.execute_for_type(log_type)
                self.stdout.write(self.style.SUCCESS(f'[{log_type}] {count} registros procesados'))
        else:
            results = use_case.execute_all()
            for log_type, count in results.items():
                self.stdout.write(self.style.SUCCESS(f'[{log_type}] {count} registros procesados'))

            if not results:
                self.stdout.write(self.style.WARNING('No hay configuraciones de retención habilitadas.'))

    @staticmethod
    def _ensure_tenant_config(config_repo: DjangoLogConfigRepository) -> None:
        """Crea la config 'tenant' con los defaults de settings si aún no existe.

        Permite que la retención de los logs por empresa funcione out-of-the-box;
        un admin puede ajustarla luego desde la plataforma.
        """
        if config_repo.get_config('tenant') is not None:
            return
        config_repo.update_config('tenant', LogRetentionConfigSchema(
            log_type='tenant',
            enabled=True,
            retention_days=getattr(settings, 'TENANT_LOG_RETENTION_DAYS', 90),
            archive_enabled=True,
            archive_after_days=30,
        ))
