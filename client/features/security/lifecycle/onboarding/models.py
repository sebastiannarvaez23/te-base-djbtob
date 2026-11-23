from django.db import models
from django.utils import timezone

from core.ids import uuid7


class CompanyRegistration(models.Model):
    """Persistent state for a multi-step company onboarding.

    Holds partial data across steps. A tenant (Company + schema) is
    created only when status transitions to COMPLETED via finalize.

    PII inside *_data JSONs expires and is purged by a scheduled job;
    the row itself is kept for metrics with status=EXPIRED.
    """

    class Status(models.TextChoices):
        IN_PROGRESS        = 'in_progress',        'In progress'
        COMPLETED          = 'completed',          'Completed'
        EXPIRED            = 'expired',            'Expired'
        FAILED_PROVISIONING = 'failed_provisioning', 'Failed provisioning'

    class Step(models.TextChoices):
        COMPANY       = 'company',       'Company'
        ADMIN_USER    = 'admin_user',    'Admin user'
        SUBSCRIPTION  = 'subscription',  'Subscription'
        PAYMENT       = 'payment',       'Payment'
        CONFIRMATION  = 'confirmation',  'Confirmation'

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.IN_PROGRESS,
        db_index=True,
    )
    # Denormalised for reporting only — StepResolver remains the source of truth.
    current_step = models.CharField(
        max_length=32, choices=Step.choices, default=Step.COMPANY,
    )

    email = models.EmailField(max_length=254, db_index=True)
    nit = models.CharField(max_length=40, blank=True, default='', db_index=True)
    schema_name = models.CharField(max_length=120, blank=True, default='', db_index=True)

    # Partial step payloads; PII lives here.
    company_data      = models.JSONField(blank=True, default=dict)
    admin_user_data   = models.JSONField(blank=True, default=dict)
    subscription_data = models.JSONField(blank=True, default=dict)
    payment_data      = models.JSONField(blank=True, default=dict)

    company_data_completed  = models.BooleanField(default=False)
    admin_user_completed    = models.BooleanField(default=False)
    subscription_selected   = models.BooleanField(default=False)
    payment_completed       = models.BooleanField(default=False)

    subscription_id   = models.UUIDField(null=True, blank=True)
    requires_payment  = models.BooleanField(default=False)

    finalized_company_id = models.UUIDField(null=True, blank=True)

    # Populated only when status=FAILED_PROVISIONING; truncated to keep the
    # row size sane.
    failure_reason = models.CharField(max_length=500, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'onboarding_company_registrations'
        verbose_name = 'Company registration'
        verbose_name_plural = 'Company registrations'
        ordering = ['-created_at']
        constraints = [
            # At most one active registration per email. Allows many COMPLETED /
            # EXPIRED rows to coexist for history and analytics.
            models.UniqueConstraint(
                fields=['email'],
                condition=models.Q(status='in_progress'),
                name='uniq_active_onboarding_email',
            ),
            # Same rule for NIT, but NIT may be empty before step COMPANY.
            models.UniqueConstraint(
                fields=['nit'],
                condition=models.Q(status='in_progress') & ~models.Q(nit=''),
                name='uniq_active_onboarding_nit',
            ),
            models.UniqueConstraint(
                fields=['schema_name'],
                condition=models.Q(status='in_progress') & ~models.Q(schema_name=''),
                name='uniq_active_onboarding_schema',
            ),
        ]

    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    def __str__(self):
        return f'{self.email} ({self.status}/{self.current_step})'
