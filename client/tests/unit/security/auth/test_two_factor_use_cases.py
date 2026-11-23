"""Unit tests for 2FA hashing, challenge issue/verify, and device binding.

The Redis store is replaced with LocMem. TrustedDevice ORM is mocked so
no database is required.
"""
import hashlib
import hmac
from unittest import TestCase, mock
from unittest.mock import MagicMock, patch

from django.core.cache.backends.locmem import LocMemCache

from core.errors import AppErrorCode, AuthException, NotFoundException


def _fresh_locmem(name: str) -> LocMemCache:
    import uuid
    return LocMemCache(f'{name}-{uuid.uuid4()}', {})


STORE_PATH = 'core.auth.two_factor_store'
MODEL_PATH = 'client.features.security.lifecycle.auth.models.TrustedDevice'
TWO_FA = 'client.features.security.lifecycle.auth.application.two_factor'


def _stub_challenge_user(mock_get_user, user):
    """``_load_challenge_user`` reloads via ``select_related('company').get()``."""
    mock_get_user.return_value.DoesNotExist = Exception
    objects = mock_get_user.return_value.objects
    objects.get.return_value = user
    objects.select_related.return_value.get.return_value = user


class TestHashHelpers(TestCase):

    def setUp(self):
        from client.features.security.lifecycle.auth.application import two_factor as tf
        self.tf = tf

    def test_otp_hash_is_hmac_sha256_hex(self):
        digest = self.tf.hash_otp('chal', '123456')
        expected = hmac.new(
            self.tf._secret(), b'chal:123456', hashlib.sha256,
        ).hexdigest()
        self.assertEqual(digest, expected)
        self.assertEqual(len(digest), 64)

    def test_device_hash_is_bound_to_user(self):
        a = self.tf.hash_device('user-a', 'serial-1-serial-1')
        b = self.tf.hash_device('user-b', 'serial-1-serial-1')
        self.assertNotEqual(a, b)

    def test_otp_is_six_digits(self):
        for _ in range(20):
            otp = self.tf.generate_otp()
            self.assertEqual(len(otp), 6)
            self.assertTrue(otp.isdigit())

    def test_mask_email_keeps_domain(self):
        self.assertEqual(self.tf.mask_email('sebastian@base.local'), '***@base.local')

    def test_parse_device_label_chrome_windows(self):
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'
        self.assertEqual(self.tf.parse_device_label(ua), 'Chrome - Windows')


class _StoreTestBase(TestCase):

    def setUp(self):
        self.cache = _fresh_locmem('2fa')
        cache_patch = mock.patch(f'{STORE_PATH}._cache', return_value=self.cache)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)

        from client.features.security.lifecycle.auth.application import two_factor as tf
        self.tf = tf

        self.user = MagicMock()
        self.user.pk = 'user-pk-1'
        self.user.email = 'seb@base.local'
        self.user.is_active = True
        self.user.username = 'seb'
        self.user.company = MagicMock()
        self.user.company.lifecycle = 'ACTIVE'

        schema_patch = mock.patch(f'{TWO_FA}.connection')
        self.conn = schema_patch.start()
        self.addCleanup(schema_patch.stop)
        self.conn.schema_name = 'tenant_a'


class TestIssueAndVerify(_StoreTestBase):

    @patch(f'{TWO_FA}.get_user_model')
    def test_issue_does_not_persist_raw_otp(self, mock_get_user):
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        stored = self.tf.two_factor_store.get(challenge.challenge_id)
        self.assertIsNotNone(stored)
        self.assertNotEqual(stored['otp_hash'], otp)
        self.assertEqual(stored['otp_hash'], self.tf.hash_otp(challenge.challenge_id, otp))
        self.assertTrue(challenge.two_factor_required)
        self.assertEqual(challenge.email_hint, '***@base.local')
        self.assertGreater(challenge.expires_in, 0)

    @patch(f'{TWO_FA}.get_user_model')
    def test_issue_stores_remember_me_on_the_challenge(self, mock_get_user):
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(
            self.user, remember_me=True,
        )
        del otp
        stored = self.tf.two_factor_store.get(challenge.challenge_id)
        self.assertTrue(stored['remember_me'])

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_returns_remember_me_from_challenge(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(
            self.user, remember_me=True,
        )
        result = self.tf.VerifyTwoFactorChallengeUseCase().execute(
            challenge.challenge_id, otp,
        )
        self.assertIs(result.user, self.user)
        self.assertTrue(result.remember_me)

    def test_stamp_updates_remember_me_on_live_challenge(self):
        _, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        self.tf.StampTwoFactorRememberMeUseCase().execute(challenge.challenge_id, True)
        stored = self.tf.two_factor_store.get(challenge.challenge_id)
        self.assertTrue(stored['remember_me'])

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_accepts_correct_otp(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)

        user = self.tf.VerifyTwoFactorChallengeUseCase().execute(
            challenge.challenge_id, otp,
        )
        self.assertIs(user.user, self.user)
        self.assertFalse(user.remember_me)
        self.assertIsNone(self.tf.two_factor_store.get(challenge.challenge_id))

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_rejects_wrong_otp(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        del otp  # unused — we submit a different code

        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, '000000',
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_INVALID)
        self.assertEqual(self.tf.two_factor_store.get_attempts(challenge.challenge_id), 1)

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_locks_after_max_attempts(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        _, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)

        for _ in range(self.tf.MAX_ATTEMPTS - 1):
            with self.assertRaises(AuthException) as ctx:
                self.tf.VerifyTwoFactorChallengeUseCase().execute(
                    challenge.challenge_id, '000000',
                )
            self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_INVALID)

        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, '000000',
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_LOCKED)
        self.assertIsNone(self.tf.two_factor_store.get(challenge.challenge_id))

    def test_verify_unknown_challenge_is_expired(self):
        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                'a' * 43, '123456',
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_EXPIRED)

    @patch(f'{TWO_FA}.get_user_model')
    def test_rotate_replaces_otp_hash(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp1, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        user, otp2, challenge2 = self.tf.RotateTwoFactorChallengeUseCase().execute(
            challenge.challenge_id,
        )
        self.assertIs(user, self.user)
        self.assertEqual(challenge2.challenge_id, challenge.challenge_id)
        self.assertNotEqual(otp1, otp2)
        stored = self.tf.two_factor_store.get(challenge.challenge_id)
        self.assertEqual(stored['otp_hash'], self.tf.hash_otp(challenge.challenge_id, otp2))
        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, otp1,
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_INVALID)

    @patch(f'{TWO_FA}.get_user_model')
    def test_new_issue_invalidates_previous_challenge(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp1, first = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        otp2, second = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        self.assertNotEqual(first.challenge_id, second.challenge_id)
        self.assertIsNone(self.tf.two_factor_store.get(first.challenge_id))
        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(first.challenge_id, otp1)
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_EXPIRED)
        user = self.tf.VerifyTwoFactorChallengeUseCase().execute(second.challenge_id, otp2)
        self.assertIs(user.user, self.user)

    @patch(f'{TWO_FA}.get_user_model')
    def test_expired_payload_is_deleted(self, mock_get_user):
        _, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        stored = self.tf.two_factor_store.get(challenge.challenge_id)
        stored['expires_at'] = '2000-01-01T00:00:00+00:00'
        self.tf.two_factor_store.put(challenge.challenge_id, stored, ttl_seconds=60)
        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, '123456',
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_EXPIRED)
        self.assertIsNone(self.tf.two_factor_store.get(challenge.challenge_id))

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_rejects_ip_mismatch(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(
            self.user, ip='10.0.0.1',
        )
        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, otp, ip='10.0.0.2',
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_EXPIRED)
        self.assertIsNone(self.tf.two_factor_store.get(challenge.challenge_id))

    def test_client_ip_ignores_forwarded_header_by_default(self):
        request = mock.Mock()
        request.META = {
            'HTTP_X_FORWARDED_FOR': '1.2.3.4',
            'REMOTE_ADDR': '10.0.0.9',
        }
        with mock.patch.object(self.tf.settings, 'TRUST_X_FORWARDED_FOR', False, create=True):
            self.assertEqual(self.tf.client_ip(request), '10.0.0.9')

    def test_client_ip_uses_first_forwarded_hop_when_trusted(self):
        request = mock.Mock()
        request.META = {
            'HTTP_X_FORWARDED_FOR': '1.2.3.4, 10.0.0.1',
            'REMOTE_ADDR': '10.0.0.9',
        }
        with mock.patch.object(self.tf.settings, 'TRUST_X_FORWARDED_FOR', True, create=True):
            self.assertEqual(self.tf.client_ip(request), '1.2.3.4')

    def test_geo_headers_ignored_by_default(self):
        request = mock.Mock()
        request.META = {
            'HTTP_CF_IPCITY': 'Cali',
            'HTTP_CF_IPCOUNTRY': 'CO',
        }
        with mock.patch.object(self.tf.settings, 'TRUST_GEO_HEADERS', False, create=True):
            self.assertEqual(self.tf.resolve_login_location(request), 'Unknown location')

    def test_geo_headers_used_when_trusted(self):
        request = mock.Mock()
        request.META = {
            'HTTP_CF_IPCITY': 'Cali',
            'HTTP_CF_IPCOUNTRY': 'CO',
        }
        with mock.patch.object(self.tf.settings, 'TRUST_GEO_HEADERS', True, create=True):
            self.assertEqual(self.tf.resolve_login_location(request), 'Cali, CO')

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_accepts_matching_ip(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(
            self.user, ip='10.0.0.1',
        )
        user = self.tf.VerifyTwoFactorChallengeUseCase().execute(
            challenge.challenge_id, otp, ip='10.0.0.1',
        )
        self.assertIs(user.user, self.user)

    @patch(f'{TWO_FA}.get_user_model')
    def test_rotate_does_not_reset_attempt_counter(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        del otp

        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, '000000',
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_INVALID)
        self.assertEqual(self.tf.two_factor_store.get_attempts(challenge.challenge_id), 1)

        self.tf.RotateTwoFactorChallengeUseCase().execute(challenge.challenge_id)
        self.assertEqual(self.tf.two_factor_store.get_attempts(challenge.challenge_id), 1)

        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, '000000',
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_INVALID)
        self.assertEqual(self.tf.two_factor_store.get_attempts(challenge.challenge_id), 2)

    @patch(f'{TWO_FA}.get_user_model')
    def test_get_active_returns_live_challenge(self, mock_get_user):
        _, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        active = self.tf.GetActiveTwoFactorChallengeUseCase().execute(self.user)
        self.assertIsNotNone(active)
        self.assertEqual(active.challenge_id, challenge.challenge_id)

    def test_get_active_returns_none_when_expired(self):
        _, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        stored = self.tf.two_factor_store.get(challenge.challenge_id)
        stored['expires_at'] = '2000-01-01T00:00:00+00:00'
        self.tf.two_factor_store.put(challenge.challenge_id, stored, ttl_seconds=60)
        self.assertIsNone(self.tf.GetActiveTwoFactorChallengeUseCase().execute(self.user))

    def test_get_active_returns_none_without_challenge(self):
        self.assertIsNone(self.tf.GetActiveTwoFactorChallengeUseCase().execute(self.user))

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_rejects_schema_mismatch(self, mock_get_user):
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        self.conn.schema_name = 'tenant_b'
        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, otp,
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_OTP_EXPIRED)

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_rejects_inactive_user(self, mock_get_user):
        self.user.is_active = False
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, otp,
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_ACCOUNT_INACTIVE)

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_rejects_closed_company(self, mock_get_user):
        self.user.company.lifecycle = 'GONE'
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        with self.assertRaises(AuthException) as ctx:
            self.tf.VerifyTwoFactorChallengeUseCase().execute(
                challenge.challenge_id, otp,
            )
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_COMPANY_CLOSED)

    @patch(f'{TWO_FA}.get_user_model')
    def test_verify_does_not_recheck_email_verified_at(self, mock_get_user):
        self.user.email_verified_at = None
        _stub_challenge_user(mock_get_user, self.user)
        otp, challenge = self.tf.IssueTwoFactorChallengeUseCase().execute(self.user)
        user = self.tf.VerifyTwoFactorChallengeUseCase().execute(
            challenge.challenge_id, otp,
        )
        self.assertIs(user.user, self.user)


class TestTrustedDeviceLookup(TestCase):

    def setUp(self):
        from client.features.security.lifecycle.auth.application import two_factor as tf
        self.tf = tf
        self.user = MagicMock()
        self.user.pk = 'user-pk-1'

    def test_missing_serial_is_untrusted(self):
        self.assertIsNone(self.tf.FindTrustedDeviceUseCase().execute(self.user, None))
        self.assertIsNone(self.tf.FindTrustedDeviceUseCase().execute(self.user, 'short'))

    @patch(MODEL_PATH)
    def test_lookup_uses_user_bound_hash(self, model):
        model.objects.filter.return_value.first.return_value = MagicMock()
        serial = 'a' * 32
        self.tf.FindTrustedDeviceUseCase().execute(self.user, serial)
        kwargs = model.objects.filter.call_args.kwargs
        self.assertEqual(kwargs['device_hash'], self.tf.hash_device(self.user.pk, serial))
        self.assertTrue(kwargs['revoked_at__isnull'])
        self.assertEqual(kwargs['user'], self.user)


def _stub_atomic(atomic):
    atomic.return_value.__enter__.return_value = None
    atomic.return_value.__exit__.return_value = False


class TestRegisterTrustedDevice(TestCase):

    def setUp(self):
        from client.features.security.lifecycle.auth.application import two_factor as tf
        self.tf = tf
        self.user = MagicMock()
        self.user.pk = 'user-pk-1'

    @patch(MODEL_PATH)
    @patch(f'{TWO_FA}.transaction.atomic')
    def test_invalid_serial_does_not_touch_orm(self, atomic, model):
        _stub_atomic(atomic)
        self.tf.RegisterTrustedDeviceUseCase().execute(self.user, 'short')
        model.objects.select_for_update.assert_not_called()

    @patch(MODEL_PATH)
    @patch(f'{TWO_FA}.transaction.atomic')
    def test_create_binds_hash_to_user(self, atomic, model):
        _stub_atomic(atomic)
        device = MagicMock()
        sfu = MagicMock()
        sfu.get_or_create.return_value = (device, True)
        sfu.filter.return_value.order_by.return_value = [device]
        model.objects.select_for_update.return_value = sfu

        serial = 'a' * 32
        self.tf.RegisterTrustedDeviceUseCase().execute(
            self.user, serial, ip='10.0.0.1',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
        )

        kwargs = sfu.get_or_create.call_args.kwargs
        self.assertEqual(kwargs['user'], self.user)
        self.assertEqual(kwargs['device_hash'], self.tf.hash_device(self.user.pk, serial))
        self.assertIsNone(kwargs['defaults']['revoked_at'])
        self.assertEqual(kwargs['defaults']['label'], 'Chrome - Windows')

    @patch(MODEL_PATH)
    @patch(f'{TWO_FA}.transaction.atomic')
    def test_existing_serial_unrevokes_and_touches(self, atomic, model):
        _stub_atomic(atomic)
        device = MagicMock()
        device.label = 'Old'
        sfu = MagicMock()
        sfu.get_or_create.return_value = (device, False)
        sfu.filter.return_value.order_by.return_value = [device]
        model.objects.select_for_update.return_value = sfu

        self.tf.RegisterTrustedDeviceUseCase().execute(self.user, 'a' * 32, ip='8.8.8.8')

        self.assertIsNone(device.revoked_at)
        self.assertEqual(device.last_ip, '8.8.8.8')
        device.save.assert_called_once()
        self.assertIn('revoked_at', device.save.call_args.kwargs['update_fields'])
        self.assertIn('last_used_at', device.save.call_args.kwargs['update_fields'])

    @patch(MODEL_PATH)
    @patch(f'{TWO_FA}.transaction.atomic')
    def test_overflow_revokes_least_recently_used(self, atomic, model):
        _stub_atomic(atomic)
        newest = MagicMock()
        oldest = MagicMock()
        rest = [MagicMock() for _ in range(self.tf.MAX_TRUSTED_DEVICES - 1)]
        sfu = MagicMock()
        sfu.get_or_create.return_value = (newest, True)
        sfu.filter.return_value.order_by.return_value = [oldest, *rest, newest]
        model.objects.select_for_update.return_value = sfu

        self.tf.RegisterTrustedDeviceUseCase().execute(self.user, 'a' * 32)

        self.assertIsNotNone(oldest.revoked_at)
        oldest.save.assert_called()
        self.assertEqual(oldest.save.call_args.kwargs['update_fields'], ['revoked_at'])
        newest.save.assert_not_called()


class TestListAndRevokeTrustedDevices(TestCase):

    def setUp(self):
        from django.utils import timezone
        from client.features.security.lifecycle.auth.application import two_factor as tf
        self.tf = tf
        self.user = MagicMock()
        self.user.pk = 'user-pk-1'
        self.now = timezone.now()

    def _row(self, *, pk, label, serial=None, digest=None):
        row = MagicMock()
        row.id = pk
        row.label = label
        row.last_ip = '1.1.1.1'
        row.last_used_at = self.now
        row.created_at = self.now
        row.device_hash = digest or self.tf.hash_device(self.user.pk, serial)
        row.revoked_at = None
        return row

    @patch(MODEL_PATH)
    def test_list_marks_current_serial(self, model):
        serial = 'a' * 32
        current = self._row(pk='11111111-1111-1111-1111-111111111111', label='Chrome - Windows', serial=serial)
        other = self._row(pk='22222222-2222-2222-2222-222222222222', label='Firefox - Linux', digest='other-hash')
        model.objects.filter.return_value.order_by.return_value = [current, other]

        devices = self.tf.ListTrustedDevicesUseCase().execute(self.user, serial)

        self.assertEqual(len(devices), 2)
        self.assertTrue(devices[0].is_current)
        self.assertEqual(devices[0].label, 'Chrome - Windows')
        self.assertFalse(devices[1].is_current)

    @patch(MODEL_PATH)
    def test_revoke_marks_row(self, model):
        row = MagicMock()
        row.device_hash = 'deadbeef'
        model.objects.filter.return_value.first.return_value = row

        digest = self.tf.RevokeTrustedDeviceUseCase().execute(self.user, 'dev-id')

        self.assertEqual(digest, 'deadbeef')
        self.assertIsNotNone(row.revoked_at)
        row.save.assert_called_once_with(update_fields=['revoked_at'])

    @patch(MODEL_PATH)
    def test_revoke_missing_raises_not_found(self, model):
        model.objects.filter.return_value.first.return_value = None
        with self.assertRaises(NotFoundException) as ctx:
            self.tf.RevokeTrustedDeviceUseCase().execute(self.user, 'missing')
        self.assertEqual(ctx.exception.code, AppErrorCode.AUTH_DEVICE_NOT_FOUND)


class TestTwoFactorStore(_StoreTestBase):

    def test_incr_attempts_counts_up(self):
        self.assertEqual(self.tf.two_factor_store.incr_attempts('cid-1', 60), 1)
        self.assertEqual(self.tf.two_factor_store.incr_attempts('cid-1', 60), 2)
        self.assertEqual(self.tf.two_factor_store.get_attempts('cid-1'), 2)

    def test_replace_for_user_deletes_previous_challenge(self):
        first_id = 'first-challenge-id'
        second_id = 'second-challenge-id'
        payload = {
            'user_id': self.user.pk,
            'schema_name': 'tenant_a',
            'otp_hash': 'abc',
            'attempts': 0,
        }
        self.tf.two_factor_store.replace_for_user(
            'tenant_a', self.user.pk, first_id, payload, ttl_seconds=60,
        )
        self.tf.two_factor_store.replace_for_user(
            'tenant_a', self.user.pk, second_id, payload, ttl_seconds=60,
        )
        self.assertIsNone(self.tf.two_factor_store.get(first_id))
        self.assertIsNotNone(self.tf.two_factor_store.get(second_id))
        self.assertEqual(
            self.tf.two_factor_store.get_active_id('tenant_a', self.user.pk),
            second_id,
        )
