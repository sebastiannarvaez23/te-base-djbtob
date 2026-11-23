"""Live support chat sessions — public schema (cross-tenant admin attention)."""

from django.db import models
from django.db.models import Q

from core.ids import uuid7
from platform.features.support.sessions.session.domain import constants as c


class SupportSettings(models.Model):
    """Singleton: queue wait policy and alternate contact channels for support."""

    SINGLETON_KEY = 'default'
    DEFAULT_QUEUE_WAIT_MINUTES = c.DEFAULT_QUEUE_WAIT_MINUTES

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    singleton_key = models.CharField(
        max_length=16,
        unique=True,
        default=SINGLETON_KEY,
        editable=False,
    )
    queue_wait_timeout_minutes = models.PositiveSmallIntegerField(
        default=DEFAULT_QUEUE_WAIT_MINUTES,
        help_text='Minutes to wait for an agent while QUEUED before timing out.',
    )
    whatsapp_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text='Redirect URL to the WhatsApp support channel.',
    )
    phone_line = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Support phone line shown to the operator on queue timeout.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support_session'
        db_table = 'support_settings'
        constraints = [
            models.CheckConstraint(
                check=models.Q(queue_wait_timeout_minutes__gte=1)
                & models.Q(queue_wait_timeout_minutes__lte=180),
                name='chk_sup_settings_queue_wait_minutes',
            ),
        ]

    def __str__(self) -> str:
        return (
            f'SupportSettings wait={self.queue_wait_timeout_minutes}m '
            f'wa={bool(self.whatsapp_url)} phone={bool(self.phone_line)}'
        )


class SupportSession(models.Model):
    STATUS_QUEUED = c.STATUS_QUEUED
    STATUS_ACTIVE = c.STATUS_ACTIVE
    STATUS_AWAITING_RATING = c.STATUS_AWAITING_RATING
    STATUS_CLOSED = c.STATUS_CLOSED
    STATUS_CANCELLED = c.STATUS_CANCELLED
    STATUS_CHOICES = list(c.STATUS_CHOICES)
    OPEN_STATUSES = c.OPEN_STATUSES

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)

    company_id = models.CharField(max_length=64, db_index=True)
    schema_name = models.CharField(max_length=63, db_index=True)
    company_name = models.CharField(max_length=200, blank=True, default='')

    requester_user_id = models.UUIDField(db_index=True)
    requester_username = models.CharField(max_length=150, blank=True, default='')
    requester_display_name = models.CharField(max_length=200, blank=True, default='')

    motive = models.CharField(max_length=4000)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
        db_index=True,
    )

    accepted_by_id = models.UUIDField(null=True, blank=True, db_index=True)
    accepted_by_label = models.CharField(max_length=200, blank=True, default='')

    client_unread_count = models.PositiveIntegerField(default=0)
    agent_unread_count = models.PositiveIntegerField(default=0)

    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_comment = models.CharField(max_length=500, blank=True, default='')

    queued_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    rated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support_session'
        db_table = 'support_sessions'
        ordering = ['-queued_at']
        indexes = [
            models.Index(
                fields=['requester_user_id', 'status'],
                name='sup_sess_req_status_idx',
            ),
            models.Index(
                fields=['accepted_by_id', 'status'],
                name='sup_sess_agent_status_idx',
            ),
            models.Index(fields=['-queued_at'], name='sup_sess_queued_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['requester_user_id'],
                condition=Q(status__in=list(c.OPEN_STATUSES)),
                name=c.UQ_OPEN_REQUESTER,
            ),
            models.UniqueConstraint(
                fields=['accepted_by_id'],
                condition=Q(status=c.STATUS_ACTIVE),
                name=c.UQ_ACTIVE_AGENT,
            ),
            models.CheckConstraint(
                check=Q(rating__isnull=True) | (Q(rating__gte=1) & Q(rating__lte=5)),
                name='chk_sup_sess_rating_range',
            ),
        ]

    def __str__(self):
        return f'SupportSession {self.id} · {self.status}'


class SupportSessionMessage(models.Model):
    SENDER_CLIENT = c.SENDER_CLIENT
    SENDER_AGENT = c.SENDER_AGENT
    SENDER_SYSTEM = c.SENDER_SYSTEM
    SENDER_CHOICES = [
        (SENDER_CLIENT, 'Client'),
        (SENDER_AGENT, 'Agent'),
        (SENDER_SYSTEM, 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    session = models.ForeignKey(
        SupportSession,
        on_delete=models.DO_NOTHING,
        related_name='messages',
    )
    sender_kind = models.CharField(max_length=10, choices=SENDER_CHOICES)
    sender_user_id = models.UUIDField(null=True, blank=True)
    body = models.CharField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support_session'
        db_table = 'support_session_messages'
        ordering = ['created_at']
        indexes = [
            models.Index(
                fields=['session', 'created_at'],
                name='sup_sess_msg_created_idx',
            ),
        ]


class SupportSessionEvent(models.Model):
    EVENT_CREATED = 'CREATED'
    EVENT_QUEUED = 'QUEUED'
    EVENT_ACCEPTED = 'ACCEPTED'
    # Legacy rows may still carry MESSAGE; new code no longer writes them.
    EVENT_MESSAGE = 'MESSAGE'
    EVENT_CLOSED = 'CLOSED'
    EVENT_RATED = 'RATED'
    EVENT_CANCELLED = 'CANCELLED'
    EVENT_ACCEPT_CONFLICT = 'ACCEPT_CONFLICT'
    EVENT_CHOICES = [
        (EVENT_CREATED, 'Created'),
        (EVENT_QUEUED, 'Queued'),
        (EVENT_ACCEPTED, 'Accepted'),
        (EVENT_MESSAGE, 'Message'),
        (EVENT_CLOSED, 'Closed'),
        (EVENT_RATED, 'Rated'),
        (EVENT_CANCELLED, 'Cancelled'),
        (EVENT_ACCEPT_CONFLICT, 'Accept conflict'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    session = models.ForeignKey(
        SupportSession,
        on_delete=models.DO_NOTHING,
        related_name='events',
    )
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    actor_kind = models.CharField(max_length=10, blank=True, default='')
    actor_user_id = models.UUIDField(null=True, blank=True)
    actor_label = models.CharField(max_length=200, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support_session'
        db_table = 'support_session_events'
        ordering = ['created_at']
        indexes = [
            models.Index(
                fields=['session', 'created_at'],
                name='sup_sess_evt_created_idx',
            ),
        ]
