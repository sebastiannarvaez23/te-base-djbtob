"""Accesos otorgados a usuarios sobre entidades operativas (schema tenant).

``user_id`` sin FK: el usuario vive en el schema público.
"""
from django.db import models

from core.ids import uuid7


class EntityGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user_id = models.UUIDField()
    entity_type = models.CharField(max_length=32)
    entity_id = models.UUIDField()
    granted_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'security_entity_grants'
        constraints = [
            models.UniqueConstraint(
                fields=['user_id', 'entity_type', 'entity_id'],
                name='egrant_user_entity_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['entity_type', 'entity_id'], name='egrant_entity_idx'),
        ]

    def __str__(self):
        return f'{self.entity_type}:{self.entity_id} · user={self.user_id}'
