"""Unit tests for email confirmation use cases.

Covers the pair responsible for flipping ``user.email_verified_at``:

  * ``IssueEmailConfirmationTokenUseCase`` — supersedes outstanding active
    tokens for the user (single-shot semantics), creates a new row with
    ``sha256(raw)`` and returns the raw token. Raw value is never stored.
  * ``ConfirmEmailUseCase`` — hashes the presented token, looks it up,
    asserts the record is consumable, marks it used, and sets
    ``email_verified_at`` on the user (idempotent if already verified).

The ORM manager is replaced with a Mock; no database is required.
Hash determinism is exercised directly as a regression guard — if the
hash algorithm ever changed, previously issued tokens would stop
matching and the flow would silently break.
"""
import hashlib
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors import AppErrorCode, AuthException
from client.features.security.lifecycle.auth.application.email_confirmation import (
    ConfirmEmailUseCase,
    IssueEmailConfirmationTokenUseCase,
    _hash_token,
)

# The use cases import the ORM model inside ``execute()`` (lazy import to keep
# the application layer free of concrete Django-model references at import
# time). That means patching its canonical location in ``auth.models`` is what
# intercepts the calls.
_MODEL_PATH = 'client.features.security.lifecycle.auth.models.EmailConfirmationToken'


# ── Hash helper ──────────────────────────────────────────────────────────────

class TestHashToken(TestCase):
    """The hash is the persistence key. Changing algorithm == breaking
    every outstanding email link; pin it."""

    def test_is_sha256_hex(self):
        digest = _hash_token('hello')
        self.assertEqual(digest, hashlib.sha256(b'hello').hexdigest())

    def test_deterministic(self):
        self.assertEqual(_hash_token('same'), _hash_token('same'))

    def test_different_inputs_produce_different_hashes(self):
        self.assertNotEqual(_hash_token('a'), _hash_token('b'))

    def test_hex_length_is_64_chars(self):
        self.assertEqual(len(_hash_token('any-input')), 64)


# ── Issue use case ───────────────────────────────────────────────────────────

class TestIssueEmailConfirmationTokenUseCase(TestCase):

    def setUp(self):
        self.user = MagicMock()
        self.uc = IssueEmailConfirmationTokenUseCase(ttl_hours=24)

    @patch(_MODEL_PATH)
    def test_returns_raw_token_string(self, model):
        model.objects.filter.return_value.update.return_value = 0
        raw = self.uc.execute(self.user)
        self.assertIsInstance(raw, str)
        self.assertGreater(len(raw), 20)

    @patch(_MODEL_PATH)
    def test_raw_tokens_are_unique_across_calls(self, model):
        model.objects.filter.return_value.update.return_value = 0
        a = self.uc.execute(self.user)
        b = self.uc.execute(self.user)
        self.assertNotEqual(a, b)

    @patch(_MODEL_PATH)
    def test_persists_only_the_hash_not_the_raw_value(self, model):
        """Regression guard: we must never store the raw token — the whole
        point of hashing is that a DB leak cannot resurrect live links."""
        model.objects.filter.return_value.update.return_value = 0
        raw = self.uc.execute(self.user)

        model.objects.create.assert_called_once()
        kwargs = model.objects.create.call_args.kwargs
        self.assertNotIn(raw, kwargs.values())
        self.assertEqual(kwargs['token_hash'], _hash_token(raw))

    @patch(_MODEL_PATH)
    def test_supersedes_outstanding_active_tokens_for_same_user(self, model):
        """Single-shot: issuing a fresh token invalidates any previous
        un-used ones so a leaked older email link cannot be redeemed."""
        self.uc.execute(self.user)

        model.objects.filter.assert_called_once_with(
            user=self.user, used_at__isnull=True,
        )
        model.objects.filter.return_value.update.assert_called_once()
        update_kwargs = model.objects.filter.return_value.update.call_args.kwargs
        self.assertIn('used_at', update_kwargs)

    @patch(_MODEL_PATH)
    def test_expires_at_follows_configured_ttl_hours(self, model):
        from datetime import timedelta
        from django.utils import timezone

        uc = IssueEmailConfirmationTokenUseCase(ttl_hours=3)
        before = timezone.now()
        uc.execute(self.user)
        after = timezone.now()

        expires_at = model.objects.create.call_args.kwargs['expires_at']
        # Give a generous window for clock resolution.
        self.assertGreaterEqual(expires_at, before + timedelta(hours=3) - timedelta(seconds=1))
        self.assertLessEqual(expires_at, after + timedelta(hours=3) + timedelta(seconds=1))


# ── Confirm use case ─────────────────────────────────────────────────────────

class TestConfirmEmailUseCase(TestCase):

    def setUp(self):
        self.uc = ConfirmEmailUseCase()

    def _record(self, consumable=True, verified=False):
        user = MagicMock()
        user.email_verified_at = None if not verified else MagicMock()
        rec = MagicMock()
        rec.user = user
        rec.is_consumable.return_value = consumable
        rec.used_at = None
        return rec

    @patch(_MODEL_PATH)
    def test_flips_email_verified_when_token_is_consumable(self, model):
        record = self._record()
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        user = self.uc.execute('raw-token')

        self.assertIsNotNone(user.email_verified_at)
        user.save.assert_called_once_with(update_fields=['email_verified_at'])

    @patch(_MODEL_PATH)
    def test_marks_token_used_when_consumed(self, model):
        record = self._record()
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        self.uc.execute('raw-token')

        self.assertIsNotNone(record.used_at)
        record.save.assert_called_once_with(update_fields=['used_at'])

    @patch(_MODEL_PATH)
    def test_lookup_uses_hashed_token_not_raw(self, model):
        """Belt-and-braces: the persistence layer never sees the raw value."""
        record = self._record()
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        self.uc.execute('raw-token')

        model.objects.select_related.return_value.filter.assert_called_once_with(
            token_hash=_hash_token('raw-token'),
        )

    @patch(_MODEL_PATH)
    def test_raises_when_token_not_found(self, model):
        model.objects.select_related.return_value.filter.return_value.first.return_value = None

        with self.assertRaises(AuthException) as ctx:
            self.uc.execute('never-issued')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_TOKEN_INVALID)

    @patch(_MODEL_PATH)
    def test_raises_when_token_already_used(self, model):
        record = self._record(consumable=False)
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        with self.assertRaises(AuthException) as ctx:
            self.uc.execute('raw-token')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_TOKEN_INVALID)

    @patch(_MODEL_PATH)
    def test_replay_is_rejected_by_is_consumable(self, model):
        """Second consumption fails once the row has ``used_at`` set —
        delegated to ``is_consumable``; here we assert we honor it."""
        record = self._record(consumable=False)
        model.objects.select_related.return_value.filter.return_value.first.return_value = record
        with self.assertRaises(AuthException):
            self.uc.execute('already-used')

    @patch(_MODEL_PATH)
    def test_idempotent_when_email_already_verified(self, model):
        """If the user was verified by another token first, don't overwrite
        ``email_verified_at`` — the earlier timestamp is more accurate."""
        record = self._record(verified=True)
        original_ts = record.user.email_verified_at
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        user = self.uc.execute('raw-token')

        self.assertIs(user.email_verified_at, original_ts)
        user.save.assert_not_called()
