"""Domain constants for live support sessions (no Django / ORM)."""

from __future__ import annotations

# ── Status ──────────────────────────────────────────────────────────────────

STATUS_QUEUED = 'QUEUED'
STATUS_ACTIVE = 'ACTIVE'
STATUS_AWAITING_RATING = 'AWAITING_RATING'
STATUS_CLOSED = 'CLOSED'
STATUS_CANCELLED = 'CANCELLED'

STATUS_CHOICES = (
    (STATUS_QUEUED, 'Queued'),
    (STATUS_ACTIVE, 'Active'),
    (STATUS_AWAITING_RATING, 'Awaiting rating'),
    (STATUS_CLOSED, 'Closed'),
    (STATUS_CANCELLED, 'Cancelled'),
)

OPEN_STATUSES = (
    STATUS_QUEUED,
    STATUS_ACTIVE,
    STATUS_AWAITING_RATING,
)

# ── Sender ──────────────────────────────────────────────────────────────────

SENDER_CLIENT = 'CLIENT'
SENDER_AGENT = 'AGENT'
SENDER_SYSTEM = 'SYSTEM'

# ── System copy (English; clients i18n via codes / UI) ───────────────────────

ASK_MOTIVE_MESSAGE = (
    'Tell us why you are contacting us: which screen you were on, '
    'what you were trying to do and what message you saw.'
)
AGENT_JOINED_MESSAGE = 'An agent has joined this conversation'
RATING_REQUEST_MESSAGE = 'Please rate the support you received'

# ── Policy defaults ─────────────────────────────────────────────────────────

DEFAULT_QUEUE_WAIT_MINUTES = 10
AWAITING_RATING_TTL_HOURS = 72
ADMIN_IDS_CACHE_TTL_SECONDS = 60
ADMIN_IDS_CACHE_KEY = 'support:active_admin_ids'

# Partial unique index names (IntegrityError mapping)
UQ_OPEN_REQUESTER = 'uq_sup_sess_open_requester'
UQ_ACTIVE_AGENT = 'uq_sup_sess_active_agent'
