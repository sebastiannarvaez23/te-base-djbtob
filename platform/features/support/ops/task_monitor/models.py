from django.db import models

from core.ids import uuid7


class AutomatedTaskRun(models.Model):
    """Una ejecución concreta de una tarea Celery instrumentada."""

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_RUNNING, 'En ejecución'),
        (STATUS_SUCCESS, 'Éxito'),
        (STATUS_FAILED, 'Fallida'),
        (STATUS_SKIPPED, 'Omitida'),
    ]

    TRIGGER_BEAT = 'beat'
    TRIGGER_MANUAL = 'manual'
    TRIGGER_HOOK = 'hook'
    TRIGGER_CHOICES = [
        (TRIGGER_BEAT, 'Beat'),
        (TRIGGER_MANUAL, 'Manual'),
        (TRIGGER_HOOK, 'Hook'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    task_key = models.CharField(max_length=120, db_index=True)
    celery_task_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    is_retry = models.BooleanField(default=False)
    retry_count = models.PositiveSmallIntegerField(default=0)
    trigger = models.CharField(
        max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_BEAT,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_summary = models.TextField(blank=True, default='')
    log_text = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automated_task_runs'
        ordering = ['-started_at', '-created_at']
        indexes = [
            models.Index(fields=['task_key', '-started_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.task_key} ({self.status})'


class AutomatedTaskStepRun(models.Model):
    """Un paso dentro de una ejecución de tarea automatizada."""

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_RUNNING, 'En ejecución'),
        (STATUS_SUCCESS, 'Éxito'),
        (STATUS_FAILED, 'Fallida'),
        (STATUS_SKIPPED, 'Omitida'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    run = models.ForeignKey(
        AutomatedTaskRun,
        on_delete=models.DO_NOTHING,
        related_name='steps',
    )
    step_key = models.CharField(max_length=80)
    order = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True, default='')
    error_detail = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'automated_task_step_runs'
        ordering = ['order', 'started_at']
        indexes = [
            models.Index(fields=['run', 'order']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['run', 'step_key'],
                name='uq_task_step_run_key',
            ),
        ]

    def __str__(self):
        return f'{self.step_key} ({self.status})'
