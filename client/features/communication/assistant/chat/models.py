"""
Historial del assistant — particionado por tenant (schema de empresa).

``AssistantConversation`` agrupa turnos de un usuario; ``AssistantMessage``
guarda user/assistant/tool; ``AssistantToolCall`` audita invocaciones de tools.
El usuario se referencia por UUID (vive en schema public).
"""


from django.db import models

from core.ids import uuid7


class AssistantConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'assistant'
        db_table = 'assistant_conversations'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user_id', '-updated_at'], name='asst_conv_user_upd_idx'),
        ]

    def __str__(self):
        return f'Conversation {self.id} · user={self.user_id}'


class AssistantMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'
        TOOL = 'tool', 'Tool'
        SYSTEM = 'system', 'System'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.DO_NOTHING,
        related_name='messages',
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'assistant'
        db_table = 'assistant_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at'], name='asst_msg_conv_created_idx'),
        ]


class AssistantToolCall(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.DO_NOTHING,
        related_name='tool_calls',
    )
    message = models.ForeignKey(
        AssistantMessage,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='tool_calls',
    )
    tool_name = models.CharField(max_length=80)
    arguments = models.JSONField(default=dict)
    result_preview = models.TextField(blank=True, default='')
    success = models.BooleanField(default=True)
    error_code = models.CharField(max_length=40, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'assistant'
        db_table = 'assistant_tool_calls'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at'], name='asst_tool_conv_created_idx'),
        ]


class AssistantAgentRun(models.Model):
    """
    Estado auditable de un turno del agente (Harness AgentRun).

    Persistido en schema tenant. La cancelación en caliente usa Redis
    (``RunCancelStore``); este modelo es la fuente de verdad al cerrar el turn.
    """

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        RUNNING = 'running', 'Running'
        AWAITING_APPROVAL = 'awaiting_approval', 'Awaiting approval'
        STREAMING = 'streaming', 'Streaming'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        FAILED = 'failed', 'Failed'
        DEGRADED = 'degraded', 'Degraded'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    conversation = models.ForeignKey(
        AssistantConversation,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='agent_runs',
    )
    user_id = models.UUIDField(db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    provider = models.CharField(max_length=40, blank=True, default='')
    model_id = models.CharField(max_length=120, blank=True, default='')
    degraded = models.BooleanField(default=False)
    cancel_requested = models.BooleanField(default=False)
    step_count = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=40, blank=True, default='')
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'assistant'
        db_table = 'assistant_agent_runs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', '-created_at'], name='asst_run_user_created_idx'),
            models.Index(fields=['status', '-created_at'], name='asst_run_status_created_idx'),
        ]
