import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_auth', '0003_emailconfirmationtoken'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PasswordRecoveryToken',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token_hash', models.CharField(db_index=True, max_length=64)),
                ('request_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('request_ua', models.CharField(blank=True, default='', max_length=512)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='password_recovery_tokens',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Password recovery token',
                'verbose_name_plural': 'Password recovery tokens',
                'db_table': 'security_password_recovery_tokens',
            },
        ),
        migrations.AddIndex(
            model_name='passwordrecoverytoken',
            index=models.Index(fields=['user', 'used_at'], name='security_pa_user_id_424668_idx'),
        ),
    ]
