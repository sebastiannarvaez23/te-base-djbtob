from django.db import models

from core.ids import uuid7


class CapabilityControlSettings(models.Model):
    """
    Singleton: kill-switch / provider stub por capacidad (forecast, vision, …).

    ``capabilities`` JSON:
      { "<cap>": { "enabled": bool, "provider": str, "notes": str } }
    """

    SINGLETON_KEY = 'default'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    singleton_key = models.CharField(
        max_length=16, unique=True, default=SINGLETON_KEY, editable=False,
    )
    capabilities = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_capability_control_settings'
        verbose_name = 'AI capability control'

    def __str__(self):
        return f'CapabilityControl n={len(self.capabilities or {})}'
