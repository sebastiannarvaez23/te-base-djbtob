from django.db import models

from core.ids import uuid7


class EmailSender(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=200, help_text='Display name for admin UI')
    email = models.EmailField(max_length=254)
    reply_to = models.EmailField(max_length=254, blank=True, default='')
    is_default = models.BooleanField(default=False, help_text='Default sender when none specified')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'communication_email_senders'
        verbose_name = 'Email sender'
        verbose_name_plural = 'Email senders'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} <{self.email}>'
