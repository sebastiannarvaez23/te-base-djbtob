"""Unit tests for migration 0013_backfill_email_verified_at.

The migration is a data migration — pure Python over an ORM queryset, no
schema change. We mock the historical ``User`` model that ``apps.get_model``
returns and assert:

  * ``forwards()`` only targets ``email_verified_at IS NULL`` rows and
    stamps them with the documented sentinel timestamp.
  * ``reverse()`` only flips rows where ``email_verified_at`` equals the
    sentinel back to ``NULL`` — never touches real verifications.
  * The sentinel itself is the exact value documented in the migration
    (``1970-01-01 00:00:01 UTC``). If anyone ever changes it inadvertently
    the test fails loudly, because re-applying with a different sentinel
    would orphan previously-backfilled rows on the next reverse.

These tests cover the contract surface, not the SQL — Django's ORM is
trusted to translate the QuerySet calls into the right UPDATE statements.
"""
import importlib
from datetime import datetime, timezone as dt_timezone
from unittest import TestCase
from unittest.mock import MagicMock

# The migration file name starts with a digit, which Python's normal
# import statement does not allow — load it via importlib instead.
_migration = importlib.import_module(
    'client.features.security.lifecycle.registration.migrations.0013_backfill_email_verified_at',
)
EMAIL_VERIFY_BACKFILL_MARKER = _migration.EMAIL_VERIFY_BACKFILL_MARKER
forwards = _migration.forwards
reverse = _migration.reverse


class TestBackfillSentinelValue(TestCase):
    """Lock the sentinel to its documented value.

    A future change to the sentinel without coordinated DB cleanup would
    leave previously-backfilled rows un-reversible (the reverse query
    looks for the *current* sentinel, not the one used at apply time).
    """

    def test_sentinel_is_unix_epoch_plus_one_second_utc(self):
        self.assertEqual(
            EMAIL_VERIFY_BACKFILL_MARKER,
            datetime(1970, 1, 1, 0, 0, 1, tzinfo=dt_timezone.utc),
        )

    def test_sentinel_is_timezone_aware(self):
        """Naive datetimes would compare incorrectly against
        ``USE_TZ=True`` storage in PostgreSQL."""
        self.assertIsNotNone(EMAIL_VERIFY_BACKFILL_MARKER.tzinfo)


class TestBackfillForwards(TestCase):

    def _apps_returning(self, user_model):
        apps = MagicMock()
        apps.get_model.return_value = user_model
        return apps

    def test_targets_only_null_rows_and_stamps_sentinel(self):
        User = MagicMock()
        forwards(self._apps_returning(User), schema_editor=MagicMock())

        User.objects.filter.assert_called_once_with(email_verified_at__isnull=True)
        User.objects.filter.return_value.update.assert_called_once_with(
            email_verified_at=EMAIL_VERIFY_BACKFILL_MARKER,
        )

    def test_resolves_the_historical_user_model(self):
        """Migrations must use ``apps.get_model``, not the live model — the
        latter could drift past the migration's frozen state."""
        User = MagicMock()
        apps = self._apps_returning(User)

        forwards(apps, schema_editor=MagicMock())

        apps.get_model.assert_called_once_with('registration', 'User')


class TestBackfillReverse(TestCase):

    def _apps_returning(self, user_model):
        apps = MagicMock()
        apps.get_model.return_value = user_model
        return apps

    def test_only_flips_sentinel_rows_back_to_null(self):
        """The whole point of the sentinel is that reverse can target the
        exact rows the forward created, without touching real verifications."""
        User = MagicMock()
        reverse(self._apps_returning(User), schema_editor=MagicMock())

        User.objects.filter.assert_called_once_with(
            email_verified_at=EMAIL_VERIFY_BACKFILL_MARKER,
        )
        User.objects.filter.return_value.update.assert_called_once_with(
            email_verified_at=None,
        )

    def test_does_not_touch_rows_with_real_verification_timestamps(self):
        """Defensive assertion: the reverse query MUST NOT use
        ``__isnull=False`` (which would wipe every verification ever
        recorded)."""
        User = MagicMock()
        reverse(self._apps_returning(User), schema_editor=MagicMock())

        call_kwargs = User.objects.filter.call_args.kwargs
        self.assertNotIn('email_verified_at__isnull', call_kwargs)
        self.assertEqual(
            call_kwargs.get('email_verified_at'),
            EMAIL_VERIFY_BACKFILL_MARKER,
        )

    def test_resolves_the_historical_user_model(self):
        User = MagicMock()
        apps = self._apps_returning(User)

        reverse(apps, schema_editor=MagicMock())

        apps.get_model.assert_called_once_with('registration', 'User')
