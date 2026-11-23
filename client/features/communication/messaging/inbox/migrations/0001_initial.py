import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('SHARE', 'Compartido por un usuario'), ('ADMIN_DIRECT', 'Admin → un usuario'), ('ADMIN_COMPANY', 'Admin → empresa'), ('ADMIN_BROADCAST', 'Admin → todas las empresas')], max_length=20)),
                ('origin_id', models.UUIDField(blank=True, null=True)),
                ('actor_kind', models.CharField(choices=[('USER', 'Usuario'), ('ADMIN', 'Administrador'), ('SYSTEM', 'Sistema')], max_length=10)),
                ('actor_id', models.UUIDField(blank=True, null=True)),
                ('actor_label', models.CharField(max_length=200)),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField(blank=True, default='')),
                ('level', models.CharField(default='INFO', max_length=20)),
                ('resource_type_code', models.CharField(blank=True, default='', max_length=80)),
                ('resource_id', models.UUIDField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Notificación',
                'verbose_name_plural': 'Notificaciones',
                'db_table': 'notifications',
            },
        ),
        migrations.CreateModel(
            name='NotificationRecipient',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user_id', models.UUIDField()),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('archived_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('notification', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='recipients', to='inbox.notification')),
            ],
            options={
                'verbose_name': 'Destinatario de notificación',
                'verbose_name_plural': 'Destinatarios de notificación',
                'db_table': 'notification_recipients',
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['-created_at'], name='notif_created_idx'),
        ),
        migrations.AddConstraint(
            model_name='notificationrecipient',
            constraint=models.UniqueConstraint(fields=('notification', 'user_id'), name='uniq_notification_user'),
        ),
        migrations.AddIndex(
            model_name='notificationrecipient',
            index=models.Index(fields=['user_id', 'read_at'], name='notif_rcpt_user_read_idx'),
        ),
        migrations.AddIndex(
            model_name='notificationrecipient',
            index=models.Index(fields=['user_id', '-created_at'], name='notif_rcpt_user_created_idx'),
        ),
    ]
