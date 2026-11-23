"""Filtros avanzados guardados por usuario y módulo operativo (schema tenant)."""
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from core.ids import uuid7
from client.features.security.identity.module_filters.domain.schemas import ModuleKey


class ModuleFilter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user_id = models.UUIDField(db_index=True)
    module_key = models.CharField(
        max_length=40,
        choices=tuple((item.value, item.value) for item in ModuleKey),
    )
    name = models.CharField(max_length=80)
    criteria = models.JSONField(default=dict)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'security_module_filters'
        indexes = [
            models.Index(fields=['user_id', 'module_key'], name='mflt_user_module_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                'user_id',
                'module_key',
                name='mflt_user_module_name_ci',
            ),
            models.UniqueConstraint(
                fields=['user_id', 'module_key'],
                condition=Q(is_active=True),
                name='mflt_user_module_active_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.module_key}:{self.name} · user={self.user_id}'
