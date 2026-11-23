# Generated manually for automated task monitor models.

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AutomatedTaskRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('task_key', models.CharField(db_index=True, max_length=120)),
                ('celery_task_id', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('running', 'En ejecución'), ('success', 'Éxito'), ('failed', 'Fallida'), ('skipped', 'Omitida')], default='pending', max_length=20)),
                ('is_retry', models.BooleanField(default=False)),
                ('retry_count', models.PositiveSmallIntegerField(default=0)),
                ('trigger', models.CharField(choices=[('beat', 'Beat'), ('manual', 'Manual'), ('hook', 'Hook')], default='beat', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('error_summary', models.TextField(blank=True, default='')),
                ('log_text', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'automated_task_runs',
                'ordering': ['-started_at', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AutomatedTaskStepRun',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('step_key', models.CharField(max_length=80)),
                ('order', models.PositiveSmallIntegerField(default=0)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('running', 'En ejecución'), ('success', 'Éxito'), ('failed', 'Fallida'), ('skipped', 'Omitida')], default='pending', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('message', models.TextField(blank=True, default='')),
                ('error_detail', models.TextField(blank=True, default='')),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='steps', to='support_task_monitor.automatedtaskrun')),
            ],
            options={
                'db_table': 'automated_task_step_runs',
                'ordering': ['order', 'started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='automatedtaskrun',
            index=models.Index(fields=['task_key', '-started_at'], name='automated_t_task_ke_idx'),
        ),
        migrations.AddIndex(
            model_name='automatedtaskrun',
            index=models.Index(fields=['status'], name='automated_t_status_idx'),
        ),
        migrations.AddIndex(
            model_name='automatedtasksteprun',
            index=models.Index(fields=['run', 'order'], name='automated_t_run_id_idx'),
        ),
        migrations.AddConstraint(
            model_name='automatedtasksteprun',
            constraint=models.UniqueConstraint(fields=('run', 'step_key'), name='uq_task_step_run_key'),
        ),
    ]
