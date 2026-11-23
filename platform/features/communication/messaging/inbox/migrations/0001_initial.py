import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='NotificationResourceType',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('code', models.CharField(max_length=80, unique=True, verbose_name='Código')),
                ('label', models.CharField(max_length=120, verbose_name='Etiqueta')),
                ('icon', models.CharField(blank=True, default='', max_length=80, verbose_name='Ícono')),
                ('route_template', models.CharField(blank=True, default='', max_length=255, verbose_name='Ruta')),
                ('is_active', models.BooleanField(default=True, verbose_name='Activo')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Tipo de recurso compartible',
                'verbose_name_plural': 'Tipos de recurso compartible',
                'db_table': 'notification_resource_types',
            },
        ),
        migrations.CreateModel(
            name='AdminNotificationOutbox',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('admin_id', models.UUIDField(verbose_name='Admin emisor')),
                ('admin_label', models.CharField(max_length=200, verbose_name='Nombre del admin')),
                ('scope', models.CharField(choices=[('SINGLE_USER', 'Un usuario'), ('COMPANY_USERS', 'Todos los usuarios de una empresa'), ('ALL_TENANTS', 'Todos los usuarios de todas las empresas')], max_length=20)),
                ('target_company_id', models.UUIDField(blank=True, null=True)),
                ('target_user_id', models.UUIDField(blank=True, null=True)),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField(blank=True, default='')),
                ('level', models.CharField(default='INFO', max_length=20)),
                ('status', models.CharField(choices=[('PENDING', 'Pendiente'), ('DISPATCHING', 'Despachando'), ('SENT', 'Enviada'), ('FAILED', 'Fallida')], default='PENDING', max_length=20)),
                ('recipients_count', models.IntegerField(default=0)),
                ('error_detail', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('dispatched_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Notificación de administrador',
                'verbose_name_plural': 'Notificaciones de administrador',
                'db_table': 'admin_notification_outbox',
            },
        ),
        migrations.AddIndex(
            model_name='adminnotificationoutbox',
            index=models.Index(fields=['-created_at'], name='admin_notif_created_idx'),
        ),
        migrations.AddIndex(
            model_name='adminnotificationoutbox',
            index=models.Index(fields=['status'], name='admin_notif_status_idx'),
        ),
    ]
