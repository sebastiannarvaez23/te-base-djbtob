"""
Estrategias de retención para logs.

DatabaseRetentionStrategy: limpia/archiva logs en tablas de base de datos.
FileRetentionStrategy: limpia logs basados en archivos (placeholder para ELK API).
"""

import gzip
import logging
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from client.features.logging.system.config.domain.schemas import LogRetentionConfigSchema
from client.features.logging.system.retention.domain.interfaces import ILogRetentionStrategy

logger = logging.getLogger('app.api')

# Fecha embebida en el nombre del archivo por empresa (YYYY-MM-DD.log[.gz]).
_TENANT_FILE_DATE = re.compile(r'(\d{4}-\d{2}-\d{2})')

# Mapeo de log_type a modelo Django
_MODEL_MAP = {
    'audit': 'client.features.logging.audit_trail.audit.models.AuditLog',
    'operations': 'client.features.logging.ops.operations.models.WarehouseEvent',
    'integration': 'client.features.logging.ops.integration.models.IntegrationLog',
    'security': 'client.features.logging.security.security.models.SecurityLog',
}


def _get_model(log_type: str):
    """Importa dinámicamente el modelo correspondiente al tipo de log."""
    model_path = _MODEL_MAP.get(log_type)
    if not model_path:
        raise ValueError(f'No model mapped for log_type: {log_type}')
    module_path, class_name = model_path.rsplit('.', 1)
    from importlib import import_module
    module = import_module(module_path)
    return getattr(module, class_name)


class DatabaseRetentionStrategy(ILogRetentionStrategy):
    """Limpia y archiva logs en base de datos según la configuración."""

    def execute_cleanup(self, log_type: str, config: LogRetentionConfigSchema) -> int:
        model = _get_model(log_type)
        cutoff = timezone.now() - timedelta(days=config.retention_days)
        qs = model.objects.filter(created_at__lt=cutoff)

        if config.max_records:
            total = model.objects.count()
            if total > config.max_records:
                excess = total - config.max_records
                excess_ids = model.objects.order_by('created_at').values_list('id', flat=True)[:excess]
                qs = qs | model.objects.filter(id__in=list(excess_ids))

        count, _ = qs.delete()
        return count

    def execute_archive(self, log_type: str, config: LogRetentionConfigSchema) -> int:
        """
        Archiva registros antiguos.
        Por defecto marca los registros (futuro: mover a tabla de archivo o exportar a S3).
        """
        if not config.archive_after_days:
            return 0

        model = _get_model(log_type)
        cutoff = timezone.now() - timedelta(days=config.archive_after_days)
        count = model.objects.filter(created_at__lt=cutoff).count()

        logger.info(
            'ARCHIVE_CANDIDATES log_type=%s count=%d cutoff=%s',
            log_type, count, cutoff.isoformat(),
        )
        return count


class FileRetentionStrategy(ILogRetentionStrategy):
    """
    Estrategia de retención para logs basados en archivos.
    Placeholder: los archivos rotativos de Python ya manejan su propio ciclo.
    Extender para integración con ELK API de limpieza de índices.
    """

    def execute_cleanup(self, log_type: str, config: LogRetentionConfigSchema) -> int:
        logger.info(
            'FILE_RETENTION_CLEANUP log_type=%s retention_days=%d (managed by rotating file handler)',
            log_type, config.retention_days,
        )
        return 0

    def execute_archive(self, log_type: str, config: LogRetentionConfigSchema) -> int:
        logger.info(
            'FILE_RETENTION_ARCHIVE log_type=%s (not applicable for file-based logs)',
            log_type,
        )
        return 0


class TenantFileRetentionStrategy(ILogRetentionStrategy):
    """
    Retención de los logs por empresa (``logs/tenants/<schema>/<YYYY-MM-DD>.log``).

    A diferencia de los archivos rotativos de Python, estos se crean uno por
    día y por empresa sin límite, por lo que necesitan limpieza explícita:

      * ``execute_archive``  → comprime a ``.log.gz`` los archivos más viejos
        que ``archive_after_days`` (nunca toca el archivo del día en curso).
      * ``execute_cleanup``  → elimina los archivos (``.log`` y ``.log.gz``)
        más viejos que ``retention_days`` y poda carpetas vacías.

    La fecha se lee del nombre del archivo, no del mtime, para ser
    determinista frente a copias/movimientos.
    """

    def _base_dir(self) -> Path:
        return Path(getattr(settings, 'TENANT_LOGS_DIR'))

    def _iter_log_files(self):
        base = self._base_dir()
        if not base.exists():
            return
        for tenant_dir in base.iterdir():
            if not tenant_dir.is_dir():
                continue
            for f in tenant_dir.iterdir():
                if f.is_file() and (f.suffix == '.log' or f.name.endswith('.log.gz')):
                    yield f

    @staticmethod
    def _file_date(f: Path):
        match = _TENANT_FILE_DATE.search(f.name)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d').date()
        except ValueError:
            return None

    def execute_archive(self, log_type: str, config: LogRetentionConfigSchema) -> int:
        if not config.archive_after_days:
            return 0

        cutoff = date.today() - timedelta(days=config.archive_after_days)
        archived = 0
        for f in list(self._iter_log_files()):
            if f.suffix != '.log':  # ya comprimido
                continue
            file_date = self._file_date(f)
            if not file_date or file_date >= cutoff:
                continue
            gz_path = f.parent / (f.name + '.gz')
            try:
                with open(f, 'rb') as src, gzip.open(gz_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                f.unlink()
                archived += 1
            except OSError as exc:
                logger.warning('TENANT_RETENTION_GZIP_FAILED file=%s error=%s', f, exc)

        logger.info('TENANT_RETENTION_ARCHIVE archived=%d cutoff=%s', archived, cutoff.isoformat())
        return archived

    def execute_cleanup(self, log_type: str, config: LogRetentionConfigSchema) -> int:
        cutoff = date.today() - timedelta(days=config.retention_days)
        deleted = 0
        for f in list(self._iter_log_files()):
            file_date = self._file_date(f)
            if not file_date or file_date >= cutoff:
                continue
            try:
                f.unlink()
                deleted += 1
            except OSError as exc:
                logger.warning('TENANT_RETENTION_UNLINK_FAILED file=%s error=%s', f, exc)

        self._prune_empty_dirs()
        logger.info(
            'TENANT_RETENTION_CLEANUP deleted=%d retention_days=%d cutoff=%s',
            deleted, config.retention_days, cutoff.isoformat(),
        )
        return deleted

    def _prune_empty_dirs(self) -> None:
        base = self._base_dir()
        if not base.exists():
            return
        for tenant_dir in base.iterdir():
            if tenant_dir.is_dir() and not any(tenant_dir.iterdir()):
                try:
                    tenant_dir.rmdir()
                except OSError:
                    pass
