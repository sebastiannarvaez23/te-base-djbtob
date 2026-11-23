import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_auth', '0002_delete_tokenmetadata'),
        ('registration', '0012_user_email_verified_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailConfirmationToken',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token_hash', models.CharField(db_index=True, max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='email_confirmation_tokens',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Email confirmation token',
                'verbose_name_plural': 'Email confirmation tokens',
                'db_table': 'security_email_confirmation_tokens',
            },
        ),
        migrations.AddIndex(
            model_name='emailconfirmationtoken',
            index=models.Index(fields=['user', 'used_at'], name='security_em_user_id_db328f_idx'),
        ),
    ]
