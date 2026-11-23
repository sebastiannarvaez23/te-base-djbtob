from django.db import models
from django.db.models import Q

from core.ids import uuid7


class AssistantSettings(models.Model):
    """Singleton de plataforma (schema público) para el assistant."""

    SINGLETON_KEY = 'default'

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    singleton_key = models.CharField(
        max_length=16, unique=True, default=SINGLETON_KEY, editable=False,
    )
    enabled = models.BooleanField(default=True)
    provider = models.CharField(max_length=20, default='local')
    max_message_chars = models.PositiveIntegerField(default=4000)
    max_agent_steps = models.PositiveSmallIntegerField(default=4)
    history_turns = models.PositiveSmallIntegerField(default=8)
    out_of_scope_message = models.CharField(max_length=200, blank=True, default='')
    require_tool_before_facts = models.BooleanField(default=True)
    enabled_tools = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assistant_settings'
        verbose_name = 'assistant settings'
        constraints = [
            models.CheckConstraint(
                check=Q(max_message_chars__gte=100) & Q(max_message_chars__lte=8000),
                name='chk_asst_max_message_chars',
            ),
            models.CheckConstraint(
                check=Q(max_agent_steps__gte=1) & Q(max_agent_steps__lte=8),
                name='chk_asst_max_agent_steps',
            ),
            models.CheckConstraint(
                check=Q(history_turns__gte=1) & Q(history_turns__lte=32),
                name='chk_asst_history_turns',
            ),
            models.CheckConstraint(
                check=Q(provider__in=['fake', 'local', 'anthropic', 'openai']),
                name='chk_asst_provider',
            ),
        ]

    def __str__(self):
        return f'AssistantSettings enabled={self.enabled} provider={self.provider}'
