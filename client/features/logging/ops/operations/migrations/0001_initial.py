import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='WarehouseEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(max_length=50, verbose_name='Tipo de evento')),
                ('zone', models.CharField(blank=True, max_length=50, null=True, verbose_name='Zona')),
                ('location', models.CharField(blank=True, max_length=100, null=True, verbose_name='Ubicación')),
                ('reference_type', models.CharField(blank=True, max_length=100, null=True, verbose_name='Tipo de referencia')),
                ('reference_id', models.CharField(blank=True, max_length=100, null=True, verbose_name='ID de referencia')),
                ('payload', models.JSONField(blank=True, null=True, verbose_name='Datos adicionales')),
                ('user_id', models.IntegerField(blank=True, null=True, verbose_name='ID de usuario')),
                ('warehouse_id', models.IntegerField(blank=True, null=True, verbose_name='ID de warehouse')),
                ('request_id', models.CharField(max_length=64, verbose_name='ID de request')),
                ('correlation_id', models.CharField(blank=True, max_length=64, null=True, verbose_name='ID de correlación')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
            ],
            options={
                'db_table': 'warehouse_events',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='warehouseevent',
            index=models.Index(fields=['event_type'], name='warehouse_e_event_t_idx'),
        ),
        migrations.AddIndex(
            model_name='warehouseevent',
            index=models.Index(fields=['warehouse_id'], name='warehouse_e_warehou_idx'),
        ),
        migrations.AddIndex(
            model_name='warehouseevent',
            index=models.Index(fields=['created_at'], name='warehouse_e_created_idx'),
        ),
        migrations.AddIndex(
            model_name='warehouseevent',
            index=models.Index(fields=['reference_type', 'reference_id'], name='warehouse_e_referen_idx'),
        ),
    ]
