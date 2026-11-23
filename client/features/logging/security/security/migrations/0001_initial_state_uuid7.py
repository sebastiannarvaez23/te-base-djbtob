# Initial state for existing ``security_logs`` table (UUID default → uuid7).

import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='SecurityLog',
                    fields=[
                        ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                        ('event_type', models.CharField(max_length=50, verbose_name='Tipo de evento')),
                        ('target_user_id', models.IntegerField(blank=True, null=True, verbose_name='ID de usuario objetivo')),
                        ('resource', models.CharField(blank=True, max_length=200, null=True, verbose_name='Recurso')),
                        ('detail', models.TextField(blank=True, null=True, verbose_name='Detalle')),
                        ('user_id', models.IntegerField(blank=True, null=True, verbose_name='ID de usuario')),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                        ('user_agent', models.TextField(blank=True, null=True, verbose_name='User Agent')),
                        ('request_id', models.CharField(max_length=64, verbose_name='ID de request')),
                        ('correlation_id', models.CharField(blank=True, max_length=64, null=True, verbose_name='ID de correlación')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                    ],
                    options={
                        'db_table': 'security_logs',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
