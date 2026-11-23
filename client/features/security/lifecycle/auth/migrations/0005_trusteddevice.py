import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_auth', '0004_passwordrecoverytoken'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TrustedDevice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('device_hash', models.CharField(max_length=64)),
                ('label', models.CharField(blank=True, default='', max_length=64)),
                ('last_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('last_ua', models.CharField(blank=True, default='', max_length=512)),
                ('last_used_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='trusted_devices',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Trusted device',
                'verbose_name_plural': 'Trusted devices',
                'db_table': 'security_trusted_devices',
            },
        ),
        migrations.AddConstraint(
            model_name='trusteddevice',
            constraint=models.UniqueConstraint(
                fields=('user', 'device_hash'),
                name='uniq_trusted_device_user_hash',
            ),
        ),
        migrations.AddIndex(
            model_name='trusteddevice',
            index=models.Index(fields=['user', 'revoked_at'], name='sec_tdev_user_revoked_idx'),
        ),
    ]
