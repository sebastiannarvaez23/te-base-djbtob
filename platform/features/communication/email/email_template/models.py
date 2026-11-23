from django.db import models

from core.ids import uuid7


class EmailTemplate(models.Model):
    """Reusable email template with HTML body and metadata."""

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    code = models.CharField(
        max_length=80, unique=True, verbose_name='Unique code',
        help_text='Machine-readable identifier (e.g. WELCOME_USER, PASSWORD_RESET).',
    )
    name = models.CharField(
        max_length=200, verbose_name='Template name',
        help_text='Human-readable label shown in the admin UI.',
    )
    subject = models.CharField(
        max_length=300, verbose_name='Email subject',
    )
    body = models.TextField(
        verbose_name='Plain-text body',
        blank=True, default='',
        help_text='Optional plain-text fallback for clients that do not render HTML.',
    )
    html_template = models.TextField(
        verbose_name='HTML template',
        help_text='Jinja2/Django-style HTML template. Use {{ variable }} for dynamic content.',
    )
    sender = models.ForeignKey(
        'email_sender.EmailSender', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='templates', verbose_name='Sender',
    )
    mock_data = models.JSONField(
        verbose_name='Mock data',
        blank=True,
        default=dict,
        help_text=(
            'Sample values for admin preview/emulation only. '
            'Never used when sending real emails — callers must supply a complete data-layer context.'
        ),
    )
    description = models.TextField(
        verbose_name='Description',
        blank=True, default='',
        help_text='Internal notes about when and how this template is used.',
    )
    is_active = models.BooleanField(
        default=True, verbose_name='Active',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        db_table = 'communication_email_templates'
        verbose_name = 'Email template'
        verbose_name_plural = 'Email templates'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'
