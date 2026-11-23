"""Backfill ``security_users.email_verified_at`` for legacy users.

Activating ``REG_EMAIL_CONFIRM=true`` in prod gates every subsequent login on
``email_verified_at IS NOT NULL``. Users created before the gate existed have
``NULL`` because the feature did not exist when they signed up — flipping the
flag without backfilling would lock them out en masse.

This migration sets a **sentinel timestamp** (``EMAIL_VERIFY_BACKFILL_MARKER``,
``1970-01-01 00:00:01 UTC``) on every user where ``email_verified_at IS NULL``.
The sentinel is distinctive enough that the reverse migration can target
exactly the rows it created, without disturbing rows verified for real.

Why the sentinel approach instead of ``NOW()``:
    - ``NOW()`` is not reversible safely — there is no way to tell apart a
      backfilled row from a real verification that happened in the same window.
    - The sentinel is far in the past and obviously not a real verification.
    - Every consumer of ``email_verified_at`` in this codebase only checks
      ``IS NULL`` / ``IS NONE`` (login gate, purge_unverified_tenants, email
      confirmation use case, repositories). None inspects the actual value,
      so a sentinel is functionally indistinguishable from ``NOW()``.

Run order:
    1. Apply this migration (``python manage.py migrate_schemas --shared``).
    2. Flip ``Parameter`` row ``REG_EMAIL_CONFIRM`` from ``false`` to ``true``.
       That is runtime config — no deploy required.
    3. Smoke test: a pre-flip account logs in successfully; a brand-new
       unverified account gets ``AUTH_007``.

Rollback:
    - Flip ``REG_EMAIL_CONFIRM`` back to ``false`` (instant; backfilled rows
      become inocuous because nothing checks the value).
    - Optionally run ``python manage.py migrate_schemas --shared registration
      0012`` to revert the data change — only flips the sentinel rows back
      to NULL, leaving real verifications intact.
"""

from datetime import datetime, timezone as dt_timezone

from django.db import migrations


EMAIL_VERIFY_BACKFILL_MARKER = datetime(1970, 1, 1, 0, 0, 1, tzinfo=dt_timezone.utc)


def forwards(apps, schema_editor):
    User = apps.get_model('registration', 'User')
    User.objects.filter(email_verified_at__isnull=True).update(
        email_verified_at=EMAIL_VERIFY_BACKFILL_MARKER,
    )


def reverse(apps, schema_editor):
    User = apps.get_model('registration', 'User')
    User.objects.filter(email_verified_at=EMAIL_VERIFY_BACKFILL_MARKER).update(
        email_verified_at=None,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0012_user_email_verified_at'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
