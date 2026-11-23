# Initial state for existing ``audit_logs`` table (UUID default → uuid7).
# Tables already exist in tenant schemas — no database CreateModel.

import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='AuditLog',
                    fields=[
                        ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                        ('entity_type', models.CharField(max_length=100, verbose_name='Tipo de entidad')),
                        ('entity_id', models.CharField(max_length=100, verbose_name='ID de entidad')),
                        ('action', models.CharField(max_length=50, verbose_name='Acción')),
                        ('changes', models.JSONField(blank=True, null=True, verbose_name='Cambios')),
                        ('description', models.TextField(blank=True, null=True, verbose_name='Descripción')),
                        ('user_id', models.IntegerField(blank=True, null=True, verbose_name='ID de usuario')),
                        ('warehouse_id', models.IntegerField(blank=True, null=True, verbose_name='ID de warehouse')),
                        ('request_id', models.CharField(max_length=64, verbose_name='ID de request')),
                        ('correlation_id', models.CharField(blank=True, max_length=64, null=True, verbose_name='ID de correlación')),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                        ('user_agent', models.TextField(blank=True, null=True, verbose_name='User Agent')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                    ],
                    options={
                        'db_table': 'audit_logs',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
