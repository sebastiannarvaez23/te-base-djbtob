import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ModelRoutingSettings',
            fields=[
                ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ('singleton_key', models.CharField(default='default', editable=False, max_length=16, unique=True)),
                ('routes', models.JSONField(blank=True, default=dict)),
                ('hourly_budget_usd', models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'AI model routing settings',
                'db_table': 'ai_model_routing_settings',
            },
        ),
    ]
