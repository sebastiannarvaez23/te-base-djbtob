"""Unit tests for password-recovery use cases.

Covers the trio that owns the password-reset flow:

  * ``IssuePasswordRecoveryTokenUseCase`` — supersedes outstanding active
    tokens for the user (single-shot), creates a row with ``sha256(raw)``
    and returns the raw token. Raw value is never stored. Audit fields
    ``request_ip`` / ``request_ua`` are persisted when provided.
  * ``ValidatePasswordRecoveryTokenUseCase`` — pure read; returns the
    user if the token is consumable AND the user is active. Never
    mutates state.
  * ``ConsumePasswordRecoveryTokenUseCase`` — atomic: validates the
    token, rotates the password via ``set_password`` (so the new hash
    is computed by Django), marks the token used.

ORM model + transaction.atomic are patched; no DB needed.
"""
import hashlib
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.errors import AppErrorCode, AuthException
from client.features.security.lifecycle.auth.application.password_recovery import (
    ConsumePasswordRecoveryTokenUseCase,
    IssuePasswordRecoveryTokenUseCase,
    ValidatePasswordRecoveryTokenUseCase,
    _hash_token,
)

# Lazy import inside execute(): patch the canonical model path.
_MODEL_PATH = 'client.features.security.lifecycle.auth.models.PasswordRecoveryToken'
_ATOMIC_PATH = 'client.features.security.lifecycle.auth.application.password_recovery.transaction.atomic'


# ── Hash helper ──────────────────────────────────────────────────────────────

class TestHashToken(TestCase):
    """The hash is the persistence key. Changing algorithm == breaking
    every outstanding reset link; pin it."""

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

class TestIssuePasswordRecoveryTokenUseCase(TestCase):

    def setUp(self):
        self.user = MagicMock()
        self.uc = IssuePasswordRecoveryTokenUseCase(ttl_minutes=60)

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
        """Regression guard: never store the raw token — the whole point
        of hashing is that a DB leak cannot resurrect live reset links."""
        model.objects.filter.return_value.update.return_value = 0
        raw = self.uc.execute(self.user)

        model.objects.create.assert_called_once()
        kwargs = model.objects.create.call_args.kwargs
        self.assertNotIn(raw, kwargs.values())
        self.assertEqual(kwargs['token_hash'], _hash_token(raw))

    @patch(_MODEL_PATH)
    def test_supersedes_outstanding_active_tokens_for_same_user(self, model):
        """Single-shot: issuing a fresh token invalidates any previous
        un-used ones so a leaked older reset link cannot be redeemed."""
        self.uc.execute(self.user)

        model.objects.filter.assert_called_once_with(
            user=self.user, used_at__isnull=True,
        )
        model.objects.filter.return_value.update.assert_called_once()
        update_kwargs = model.objects.filter.return_value.update.call_args.kwargs
        self.assertIn('used_at', update_kwargs)

    @patch(_MODEL_PATH)
    def test_expires_at_follows_configured_ttl_minutes(self, model):
        from datetime import timedelta
        from django.utils import timezone

        uc = IssuePasswordRecoveryTokenUseCase(ttl_minutes=15)
        before = timezone.now()
        uc.execute(self.user)
        after = timezone.now()

        expires_at = model.objects.create.call_args.kwargs['expires_at']
        self.assertGreaterEqual(expires_at, before + timedelta(minutes=15) - timedelta(seconds=1))
        self.assertLessEqual(expires_at, after + timedelta(minutes=15) + timedelta(seconds=1))

    @patch(_MODEL_PATH)
    def test_persists_audit_fields_when_provided(self, model):
        """``request_ip`` and ``request_ua`` are kept for abuse forensics:
        a flood of resets from one IP shows up cleanly in the audit trail."""
        self.uc.execute(self.user, request_ip='10.0.0.7', request_ua='Mozilla/5.0')
        kwargs = model.objects.create.call_args.kwargs
        self.assertEqual(kwargs['request_ip'], '10.0.0.7')
        self.assertEqual(kwargs['request_ua'], 'Mozilla/5.0')

    @patch(_MODEL_PATH)
    def test_empty_audit_fields_are_normalised(self, model):
        """Empty IP becomes None (so the model's nullable GenericIPAddress
        accepts it) and the UA defaults to ''."""
        self.uc.execute(self.user)  # nothing passed
        kwargs = model.objects.create.call_args.kwargs
        self.assertIsNone(kwargs['request_ip'])
        self.assertEqual(kwargs['request_ua'], '')

    @patch(_MODEL_PATH)
    def test_user_agent_is_truncated_to_512_chars(self, model):
        """Some bots send 2KB UA strings — cap at 512 to match the schema
        without raising on the way in."""
        self.uc.execute(self.user, request_ua='x' * 1000)
        kwargs = model.objects.create.call_args.kwargs
        self.assertEqual(len(kwargs['request_ua']), 512)


# ── Validate use case ────────────────────────────────────────────────────────

class TestValidatePasswordRecoveryTokenUseCase(TestCase):

    def setUp(self):
        self.uc = ValidatePasswordRecoveryTokenUseCase()

    def _record(self, consumable=True, active=True):
        user = MagicMock()
        user.is_active = active
        rec = MagicMock()
        rec.user = user
        rec.is_consumable.return_value = consumable
        return rec

    @patch(_MODEL_PATH)
    def test_returns_user_when_token_is_consumable(self, model):
        record = self._record()
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        user = self.uc.execute('raw-token')

        self.assertIs(user, record.user)

    @patch(_MODEL_PATH)
    def test_does_not_mutate_record(self, model):
        """Validate must not burn the token — the SPA calls this before
        showing the form, and the user still needs to consume it on submit."""
        record = self._record()
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        self.uc.execute('raw-token')

        record.save.assert_not_called()

    @patch(_MODEL_PATH)
    def test_lookup_uses_hashed_token_not_raw(self, model):
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
    def test_raises_when_token_already_used_or_expired(self, model):
        record = self._record(consumable=False)
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        with self.assertRaises(AuthException) as ctx:
            self.uc.execute('raw-token')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_TOKEN_INVALID)

    @patch(_MODEL_PATH)
    def test_raises_when_owning_user_is_inactive(self, model):
        """An attacker who grabs a reset link must not be able to rehydrate
        access for an account the admin has since deactivated."""
        record = self._record(active=False)
        model.objects.select_related.return_value.filter.return_value.first.return_value = record

        with self.assertRaises(AuthException) as ctx:
            self.uc.execute('raw-token')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_TOKEN_INVALID)


# ── Consume use case ─────────────────────────────────────────────────────────

class TestConsumePasswordRecoveryTokenUseCase(TestCase):

    def setUp(self):
        self.uc = ConsumePasswordRecoveryTokenUseCase()

    def _record(self, consumable=True, active=True):
        user = MagicMock()
        user.is_active = active
        rec = MagicMock()
        rec.user = user
        rec.is_consumable.return_value = consumable
        return rec

    def _wire_lookup(self, model, record):
        # The Consume use case does:
        #   PasswordRecoveryToken.objects.select_for_update().select_related('user').filter(...).first()
        chain = model.objects.select_for_update.return_value.select_related.return_value.filter.return_value
        chain.first.return_value = record

    @patch(_ATOMIC_PATH)
    @patch(_MODEL_PATH)
    def test_rotates_password_via_set_password_not_raw_assignment(self, model, atomic):
        """``set_password`` is what computes the Django hash; assigning to
        ``user.password`` directly would store plaintext. Pin the behavior."""
        record = self._record()
        self._wire_lookup(model, record)

        user = self.uc.execute('raw-token', new_password='S3cret-Pa$s')

        user.set_password.assert_called_once_with('S3cret-Pa$s')
        user.save.assert_called_once_with(update_fields=['password', 'password_changed_at'])

    @patch(_ATOMIC_PATH)
    @patch(_MODEL_PATH)
    def test_marks_token_used_on_success(self, model, atomic):
        record = self._record()
        self._wire_lookup(model, record)

        self.uc.execute('raw-token', new_password='S3cret-Pa$s')

        self.assertIsNotNone(record.used_at)
        record.save.assert_called_once_with(update_fields=['used_at'])

    @patch(_ATOMIC_PATH)
    @patch(_MODEL_PATH)
    def test_lookup_uses_hashed_token_not_raw(self, model, atomic):
        record = self._record()
        self._wire_lookup(model, record)

        self.uc.execute('raw-token', new_password='S3cret-Pa$s')

        filter_kwargs = model.objects.select_for_update.return_value.select_related.return_value.filter.call_args.kwargs
        self.assertEqual(filter_kwargs['token_hash'], _hash_token('raw-token'))

    @patch(_ATOMIC_PATH)
    @patch(_MODEL_PATH)
    def test_locks_row_with_select_for_update(self, model, atomic):
        """Without select_for_update two parallel confirms could both pass
        is_consumable() and double-rotate the password. The first call on
        the chain must be select_for_update."""
        record = self._record()
        self._wire_lookup(model, record)

        self.uc.execute('raw-token', new_password='S3cret-Pa$s')

        model.objects.select_for_update.assert_called_once()

    @patch(_ATOMIC_PATH)
    @patch(_MODEL_PATH)
    def test_raises_when_token_not_found(self, model, atomic):
        chain = model.objects.select_for_update.return_value.select_related.return_value.filter.return_value
        chain.first.return_value = None

        with self.assertRaises(AuthException) as ctx:
            self.uc.execute('never-issued', new_password='S3cret-Pa$s')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_TOKEN_INVALID)

    @patch(_ATOMIC_PATH)
    @patch(_MODEL_PATH)
    def test_raises_when_token_already_used_or_expired(self, model, atomic):
        record = self._record(consumable=False)
        self._wire_lookup(model, record)

        with self.assertRaises(AuthException) as ctx:
            self.uc.execute('raw-token', new_password='S3cret-Pa$s')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_TOKEN_INVALID)

    @patch(_ATOMIC_PATH)
    @patch(_MODEL_PATH)
    def test_raises_when_owning_user_is_inactive(self, model, atomic):
        record = self._record(active=False)
        self._wire_lookup(model, record)

        with self.assertRaises(AuthException) as ctx:
            self.uc.execute('raw-token', new_password='S3cret-Pa$s')

        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_TOKEN_INVALID)

    @patch(_ATOMIC_PATH)
    @patch(_MODEL_PATH)
    def test_does_not_rotate_password_when_token_invalid(self, model, atomic):
        """A failed consume must not touch the password — otherwise an
        attacker could brute-force tokens and lock the legit user out."""
        record = self._record(consumable=False)
        self._wire_lookup(model, record)

        with self.assertRaises(AuthException):
            self.uc.execute('raw-token', new_password='S3cret-Pa$s')

        record.user.set_password.assert_not_called()
        record.user.save.assert_not_called()
