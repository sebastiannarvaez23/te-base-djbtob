from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models

from core.ids import uuid7


class Testimonial(models.Model):
    """Customer quote shown on the marketing landing and managed by platform admin."""

    __test__ = False

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        related_name='testimonials',
        db_constraint=True,
        verbose_name='Author',
        help_text='Company user who wrote the testimonial.',
    )
    score = models.PositiveSmallIntegerField(
        verbose_name='Score',
        help_text='Rating from 1 to 5.',
    )
    message = models.TextField(
        verbose_name='Message',
        help_text='Testimonial body shown on the landing.',
        validators=[MaxLengthValidator(2000)],
    )
    author_name = models.CharField(
        max_length=200,
        verbose_name='Author name',
        help_text='Display name snapshot; defaults from the author user.',
    )
    author_role = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Author role',
        help_text='Job title / role shown under the quote.',
    )
    company_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Company name',
        help_text='Company snapshot; defaults from the author tenant.',
    )
    locale = models.CharField(
        max_length=2,
        default='es',
        verbose_name='Locale',
        help_text='Language of the quote (es or en).',
    )
    is_published = models.BooleanField(
        default=False,
        verbose_name='Published',
        help_text='Only published testimonials are served to the landing.',
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Sort order',
    )
    content_hash = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Content hash',
        help_text='SHA-256 of the canonical quote the author signed.',
    )
    seal = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Seal',
        help_text='HMAC seal bound to the authenticated author.',
    )
    seal_algorithm = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name='Seal algorithm',
    )
    canonical_payload = models.TextField(
        blank=True,
        default='',
        verbose_name='Canonical payload',
    )
    signed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Signed at',
    )
    signatory_id = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Signatory id',
    )
    tenant_id = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='Tenant id',
    )
    ip_address = models.CharField(max_length=64, blank=True, default='')
    user_agent = models.CharField(max_length=512, blank=True, default='')
    request_id = models.CharField(max_length=64, blank=True, default='')
    channel = models.CharField(max_length=32, blank=True, default='')
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Revoked at',
        help_text='When a newer signed quote superseded this document.',
    )
    superseded_by = models.ForeignKey(
        'self',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='supersedes',
        db_constraint=True,
        verbose_name='Superseded by',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        db_table = 'configuration_testimonials'
        verbose_name = 'Testimonial'
        verbose_name_plural = 'Testimonials'
        ordering = ['sort_order', '-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(score__gte=1, score__lte=5),
                name='chk_testimonial_score',
            ),
            models.CheckConstraint(
                check=models.Q(locale__in=['es', 'en']),
                name='chk_testimonial_locale',
            ),
            models.UniqueConstraint(
                fields=['author'],
                condition=models.Q(revoked_at__isnull=True),
                name='uniq_tst_live_author',
            ),
        ]
        indexes = [
            models.Index(
                fields=['is_published', 'sort_order'],
                name='idx_tst_published_order',
            ),
            models.Index(
                fields=['locale', 'is_published'],
                name='idx_tst_locale_pub',
            ),
            models.Index(
                fields=['is_published', 'signed_at'],
                name='idx_tst_published_signed',
            ),
            models.Index(
                fields=['author', 'revoked_at'],
                name='idx_tst_author_revoked',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.author_name} ({self.score}/5)'


class TestimonialPromptSettings(models.Model):
    """Singleton: how often company users are asked for a testimonial."""

    __test__ = False

    SINGLETON_KEY = 'default'

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    singleton_key = models.CharField(
        max_length=16, unique=True, default=SINGLETON_KEY, editable=False,
    )
    prompt_enabled = models.BooleanField(
        default=True,
        verbose_name='Prompt enabled',
        help_text='When off, the client never asks for a testimonial.',
    )
    frequency_days = models.PositiveSmallIntegerField(
        default=30,
        verbose_name='Frequency (days)',
        help_text='0 = every login until submitted; otherwise wait this many days after skip.',
    )
    first_appearance_days = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='First appearance (days)',
        help_text='Days to wait after the user first reaches the app before the first prompt. 0 = immediately.',
    )
    login_delay_seconds = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Login delay (seconds)',
        help_text='Seconds to wait after login before showing the prompt.',
    )
    ask_after_submit = models.BooleanField(
        default=False,
        verbose_name='Ask after submit',
        help_text='If off, authors who already signed are not asked again.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created at')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated at')

    class Meta:
        db_table = 'configuration_testimonial_prompt_settings'
        verbose_name = 'Testimonial prompt settings'
        constraints = [
            models.CheckConstraint(
                check=models.Q(frequency_days__lte=365),
                name='chk_tst_prompt_frequency_days',
            ),
            models.CheckConstraint(
                check=models.Q(first_appearance_days__lte=365),
                name='chk_tst_prompt_first_appearance_days',
            ),
            models.CheckConstraint(
                check=models.Q(login_delay_seconds__lte=300),
                name='chk_tst_prompt_login_delay_seconds',
            ),
        ]

    def __str__(self) -> str:
        return f'PromptSettings enabled={self.prompt_enabled} every {self.frequency_days}d'


class TestimonialPromptReceipt(models.Model):
    """Per-user last time we showed (or they skipped) the testimonial prompt."""

    __test__ = False

    id = models.UUIDField(
        primary_key=True, default=uuid7, editable=False, verbose_name='Id',
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        related_name='testimonial_prompt_receipt',
        db_constraint=True,
        verbose_name='User',
    )
    last_prompted_at = models.DateTimeField(null=True, blank=True)
    first_seen_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='First seen at',
        help_text='When the user first became a candidate for the prompt clock.',
    )
    pending_reprompt = models.BooleanField(
        default=False,
        verbose_name='Pending reprompt',
        help_text='When set, the client asks again even if the author already signed.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'configuration_testimonial_prompt_receipts'
        verbose_name = 'Testimonial prompt receipt'
