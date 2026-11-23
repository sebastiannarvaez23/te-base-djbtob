import core.ids
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AiEvalSuiteRun',
            fields=[
                ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ('suite', models.CharField(db_index=True, default='harness', max_length=40)),
                ('passed', models.PositiveIntegerField(default=0)),
                ('failed', models.PositiveIntegerField(default=0)),
                ('cases', models.JSONField(blank=True, default=list)),
                ('ran_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'AI eval suite run',
                'db_table': 'ai_eval_suite_runs',
                'ordering': ['-ran_at'],
            },
        ),
    ]
