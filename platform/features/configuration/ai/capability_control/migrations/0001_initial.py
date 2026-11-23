import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='CapabilityControlSettings',
            fields=[
                ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ('singleton_key', models.CharField(default='default', editable=False, max_length=16, unique=True)),
                ('capabilities', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'AI capability control',
                'db_table': 'ai_capability_control_settings',
            },
        ),
    ]
