# Initial state for existing ``integration_logs`` table (UUID default → uuid7).

import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='IntegrationLog',
                    fields=[
                        ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                        ('system', models.CharField(max_length=100, verbose_name='Sistema externo')),
                        ('direction', models.CharField(max_length=20, verbose_name='Dirección')),
                        ('endpoint', models.CharField(max_length=500, verbose_name='Endpoint')),
                        ('method', models.CharField(max_length=10, verbose_name='Método HTTP')),
                        ('request_body', models.JSONField(blank=True, null=True, verbose_name='Request body')),
                        ('response_body', models.JSONField(blank=True, null=True, verbose_name='Response body')),
                        ('status_code', models.IntegerField(blank=True, null=True, verbose_name='Código de estado')),
                        ('duration_ms', models.IntegerField(blank=True, null=True, verbose_name='Duración (ms)')),
                        ('error_message', models.TextField(blank=True, null=True, verbose_name='Mensaje de error')),
                        ('user_id', models.IntegerField(blank=True, null=True, verbose_name='ID de usuario')),
                        ('warehouse_id', models.IntegerField(blank=True, null=True, verbose_name='ID de warehouse')),
                        ('request_id', models.CharField(max_length=64, verbose_name='ID de request')),
                        ('correlation_id', models.CharField(blank=True, max_length=64, null=True, verbose_name='ID de correlación')),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                    ],
                    options={
                        'db_table': 'integration_logs',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
