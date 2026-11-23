# Generated manually for BYOK credentials (schema-only).

import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AssistantProviderCredential',
            fields=[
                ('id', models.UUIDField(
                    default=core.ids.uuid7, editable=False, primary_key=True, serialize=False,
                )),
                ('provider', models.CharField(
                    choices=[('openai', 'OpenAI'), ('anthropic', 'Anthropic')],
                    max_length=40,
                )),
                ('label', models.CharField(blank=True, default='', max_length=120)),
                ('ciphertext', models.BinaryField()),
                ('key_last4', models.CharField(blank=True, default='', max_length=4)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('last_validated_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.UUIDField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'assistant_provider_credentials',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='assistantprovidercredential',
            constraint=models.UniqueConstraint(
                condition=models.Q(('is_active', True)),
                fields=('provider',),
                name='asst_cred_one_active_per_provider',
            ),
        ),
    ]
