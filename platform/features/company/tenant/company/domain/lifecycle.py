"""Company tenant lifecycle — independent from subscription status."""

from __future__ import annotations

LIFECYCLE_ACTIVE = 'ACTIVE'
LIFECYCLE_CLOSED = 'CLOSED'
LIFECYCLE_PENDING_PURGE = 'PENDING_PURGE'
LIFECYCLE_GONE = 'GONE'

COMPANY_LIFECYCLES = frozenset({
    LIFECYCLE_ACTIVE,
    LIFECYCLE_CLOSED,
    LIFECYCLE_PENDING_PURGE,
    LIFECYCLE_GONE,
})
CLOSED_LIFECYCLES = frozenset({
    LIFECYCLE_CLOSED,
    LIFECYCLE_PENDING_PURGE,
    LIFECYCLE_GONE,
})
PURGEABLE_LIFECYCLES = frozenset({LIFECYCLE_CLOSED, LIFECYCLE_PENDING_PURGE})
# Purged tenants stay as a fiscal/identity row but never in operational directories.
DIRECTORY_HIDDEN_LIFECYCLES = frozenset({LIFECYCLE_GONE})

PUBLIC_SCHEMA_NAME = 'public'
DEFAULT_CLOSE_GRACE_DAYS = 30
CLOSE_GRACE_PARAM = 'DAYS_COMP_DEREGISTRA'
IMMEDIATE_PURGE_WAIVER_REASON = 'Immediate deregistration (zero grace days)'
SELF_CLOSE_PENDING_REASON = 'Self-service close'
SELF_CLOSE_ADMIN_ROLE = 'Administrator'
COMPANY_DEREGISTRATION_POLICY_CODE = 'COMPANY-DEREGISTRATION'
TENANT_STORAGE_PREFIX = 'client/tenants'
TENANT_DEREGISTRATION_FOLDER = 'deregistration'
STORAGE_BUCKET = 'base'
TOMBSTONE_EMAIL_DOMAIN = 'tombstone.invalid'


def tenant_storage_prefix(schema_name: str) -> str:
    return f'{TENANT_STORAGE_PREFIX}/{schema_name}/'


def tenant_deregistration_prefix(schema_name: str) -> str:
    return f'{tenant_storage_prefix(schema_name)}{TENANT_DEREGISTRATION_FOLDER}/'


def tenant_export_object_key(schema_name: str) -> str:
    return f'{tenant_deregistration_prefix(schema_name)}export.json'


def is_directory_visible(lifecycle: str) -> bool:
    """Operational company/user directories never include purged tenants."""
    return lifecycle not in DIRECTORY_HIDDEN_LIFECYCLES
