from django.db import models

from core.ids import uuid7


class ModelRoutingSettings(models.Model):
    """Singleton de plataforma: tabla capacidad → ruta de modelo."""

    SINGLETON_KEY = 'default'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    singleton_key = models.CharField(
        max_length=16, unique=True, default=SINGLETON_KEY, editable=False,
    )
    # {capability: {provider, model_id, fallbacks, max_tokens, timeout_s, …}}
    routes = models.JSONField(default=dict, blank=True)
    hourly_budget_usd = models.DecimalField(
        max_digits=12, decimal_places=6, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_model_routing_settings'
        verbose_name = 'AI model routing settings'

    def __str__(self):
        return f'ModelRoutingSettings budget={self.hourly_budget_usd}'
