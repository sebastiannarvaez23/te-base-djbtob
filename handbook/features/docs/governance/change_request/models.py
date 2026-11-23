"""Solicitud de cambio que apunta a una revisión completa."""

from django.db import models

from core.ids import uuid7
from handbook.core.constants import CHANGE_REQUEST_PENDING


class HandbookChangeRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    page = models.ForeignKey(
        'handbook_page.HandbookPage',
        on_delete=models.DO_NOTHING,
        related_name='change_requests',
    )
    working_revision = models.ForeignKey(
        'handbook_page.HandbookRevision',
        on_delete=models.DO_NOTHING,
        related_name='change_requests',
    )
    reason = models.TextField()
    status = models.CharField(max_length=16, default=CHANGE_REQUEST_PENDING)
    proposed_by = models.UUIDField()
    reviewed_by = models.UUIDField(null=True, blank=True)
    review_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'handbook_change_requests'
        indexes = [
            models.Index(fields=('page', 'status'), name='hbk_cr_page_status_idx'),
        ]
