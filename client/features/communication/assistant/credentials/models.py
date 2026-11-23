"""Credenciales BYOK del copiloto (ciphertext en schema tenant)."""

from django.db import models

from core.ids import uuid7


class AssistantProviderCredential(models.Model):
    class Provider(models.TextChoices):
        OPENAI = 'openai', 'OpenAI'
        ANTHROPIC = 'anthropic', 'Anthropic'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    provider = models.CharField(max_length=40, choices=Provider.choices)
    label = models.CharField(max_length=120, blank=True, default='')
    ciphertext = models.BinaryField()
    key_last4 = models.CharField(max_length=4, blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'assistant_credentials'
        db_table = 'assistant_provider_credentials'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['provider'],
                condition=models.Q(is_active=True),
                name='asst_cred_one_active_per_provider',
            ),
        ]

    def __str__(self):
        return f'{self.provider} ···{self.key_last4} active={self.is_active}'
