# Generated manually for Harness AgentRun (schema-only).

import core.ids
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assistant', '0002_alter_assistantconversation_id_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssistantAgentRun',
            fields=[
                ('id', models.UUIDField(default=core.ids.uuid7, editable=False, primary_key=True, serialize=False)),
                ('user_id', models.UUIDField(db_index=True)),
                ('status', models.CharField(
                    choices=[
                        ('queued', 'Queued'),
                        ('running', 'Running'),
                        ('awaiting_approval', 'Awaiting approval'),
                        ('streaming', 'Streaming'),
                        ('completed', 'Completed'),
                        ('cancelled', 'Cancelled'),
                        ('failed', 'Failed'),
                        ('degraded', 'Degraded'),
                    ],
                    db_index=True,
                    default='queued',
                    max_length=32,
                )),
                ('provider', models.CharField(blank=True, default='', max_length=40)),
                ('model_id', models.CharField(blank=True, default='', max_length=120)),
                ('degraded', models.BooleanField(default=False)),
                ('cancel_requested', models.BooleanField(default=False)),
                ('step_count', models.PositiveSmallIntegerField(default=0)),
                ('error_code', models.CharField(blank=True, default='', max_length=40)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('conversation', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name='agent_runs',
                    to='assistant.assistantconversation',
                )),
            ],
            options={
                'db_table': 'assistant_agent_runs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='assistantagentrun',
            index=models.Index(fields=['user_id', '-created_at'], name='asst_run_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='assistantagentrun',
            index=models.Index(fields=['status', '-created_at'], name='asst_run_status_created_idx'),
        ),
    ]
