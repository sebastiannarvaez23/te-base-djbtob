# Initial state for existing ``log_configurations`` table (UUID default → uuid7).

import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='LogConfiguration',
                    fields=[
                        ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                        ('log_type', models.CharField(choices=[('audit', 'Auditoría'), ('operations', 'Operaciones'), ('inventory', 'Inventario'), ('integration', 'Integración'), ('security', 'Seguridad'), ('errors', 'Errores'), ('performance', 'Performance'), ('system', 'Sistema'), ('tenant', 'Logs por empresa')], max_length=50, unique=True, verbose_name='Tipo de log')),
                        ('enabled', models.BooleanField(default=True, verbose_name='Habilitado')),
                        ('retention_days', models.IntegerField(default=90, verbose_name='Días de retención')),
                        ('archive_enabled', models.BooleanField(default=False, verbose_name='Archivado habilitado')),
                        ('archive_after_days', models.IntegerField(blank=True, default=60, null=True, verbose_name='Archivar después de (días)')),
                        ('max_records', models.IntegerField(blank=True, null=True, verbose_name='Máximo de registros')),
                        ('cleanup_frequency', models.CharField(choices=[('daily', 'Diario'), ('weekly', 'Semanal'), ('monthly', 'Mensual')], default='daily', max_length=20, verbose_name='Frecuencia de limpieza')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última actualización')),
                    ],
                    options={
                        'db_table': 'log_configurations',
                        'ordering': ['log_type'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
