"""Unit tests for core.auth.refresh_service — refresh token CRUD in Redis."""
from unittest import TestCase
from unittest.mock import patch, MagicMock

from core.auth.refresh_service import generate_raw_token, hash_token


class TestGenerateRawToken(TestCase):

    def test_generates_string(self):
        token = generate_raw_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 40)

    def test_unique_tokens(self):
        t1 = generate_raw_token()
        t2 = generate_raw_token()
        self.assertNotEqual(t1, t2)


class TestHashToken(TestCase):

    def test_deterministic_hash(self):
        token = 'test-token-value'
        h1 = hash_token(token)
        h2 = hash_token(token)
        self.assertEqual(h1, h2)

    def test_returns_hex_string(self):
        h = hash_token('abc')
        self.assertEqual(len(h), 64)  # SHA-256 hex = 64 chars
        int(h, 16)  # Should not raise

    def test_different_tokens_different_hashes(self):
        h1 = hash_token('token-a')
        h2 = hash_token('token-b')
        self.assertNotEqual(h1, h2)


class TestStoreAndValidate(TestCase):

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_store_sets_key_in_cache(self, mock_cache_fn, mock_redis):
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        from core.auth.refresh_service import store, hash_token
        raw = 'test-raw-token'
        result = store(
            raw_token=raw,
            user_id='user-123',
            user_type='client',
            schema_name='tenant_acme',
            ip_address='1.2.3.4',
            user_agent='Mozilla',
        )

        raw_back, token_id = result
        self.assertEqual(raw_back, raw)
        self.assertEqual(token_id, hash_token(raw)[:16])
        # Dos escrituras: el registro y su índice inverso (token_id → clave).
        self.assertEqual(cache.set.call_count, 2)
        set_keys = [c.args[0] for c in cache.set.call_args_list]
        record_key = f'rt:client:user-123:{token_id}'
        self.assertIn(record_key, set_keys)
        # El índice inverso apunta a la clave del registro.
        index_call = next(c for c in cache.set.call_args_list if c.args[0].startswith('rtid:'))
        self.assertEqual(index_call.args[0], f'rtid:client:{token_id}')
        self.assertEqual(index_call.args[1], record_key)

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_store_honours_ttl_and_remember_me(self, mock_cache_fn, mock_redis):
        import json
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        from core.auth.refresh_service import store, hash_token
        raw = 'session-raw-token'
        store(
            raw_token=raw,
            user_id='user-123',
            user_type='client',
            ttl_seconds=43200,
            remember_me=False,
        )
        record_call = next(
            c for c in cache.set.call_args_list
            if c.args[0].startswith('rt:client:')
        )
        self.assertEqual(record_call.kwargs.get('timeout') or record_call.args[2], 43200)
        payload = json.loads(record_call.args[1])
        self.assertFalse(payload['remember_me'])
        self.assertEqual(payload['hash'], hash_token(raw))

    @patch('core.auth.refresh_service.get_refresh_ttl_days', return_value=14)
    def test_refresh_ttl_seconds_caps_session_logins(self, _days):
        from core.auth.refresh_service import (
            SESSION_REFRESH_TTL_SECONDS,
            refresh_ttl_seconds,
        )
        self.assertEqual(refresh_ttl_seconds(remember_me=True), 14 * 86400)
        self.assertEqual(
            refresh_ttl_seconds(remember_me=False),
            SESSION_REFRESH_TTL_SECONDS,
        )

    def test_record_is_remembered_defaults_true_for_legacy(self):
        from core.auth.refresh_service import record_is_remembered
        self.assertTrue(record_is_remembered(None))
        self.assertTrue(record_is_remembered({'hash': 'x'}))
        self.assertFalse(record_is_remembered({'remember_me': False}))
        self.assertTrue(record_is_remembered({'remember_me': True}))

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_validate_returns_none_when_no_redis(self, mock_cache_fn, mock_redis):
        mock_redis.return_value = None

        from core.auth.refresh_service import validate
        result = validate('some-token', expected_type='client')
        self.assertIsNone(result)

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_validate_returns_none_when_no_matching_keys(self, mock_cache_fn, mock_redis):
        client = MagicMock()
        mock_redis.return_value = client
        client.scan.return_value = (0, [])
        # Índice inverso ausente → cae al SCAN de fallback, que no halla nada.
        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_fn.return_value = cache

        from core.auth.refresh_service import validate
        result = validate('some-token', expected_type='client')
        self.assertIsNone(result)

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_validate_uses_reverse_index_without_scan(self, mock_cache_fn, mock_redis):
        """Con el índice poblado, validate resuelve por GET directo y NO escanea."""
        import json
        from core.auth.refresh_service import validate, hash_token, _index_key

        raw = 'some-raw-token'
        token_id = hash_token(raw)[:16]
        record_key = f'rt:client:user-9:{token_id}'
        record = {'hash': hash_token(raw), 'user_id': 'user-9', 'user_type': 'client'}

        client = MagicMock()
        mock_redis.return_value = client

        cache = MagicMock()

        def _get(key):
            if key == _index_key('client', token_id):
                return record_key
            if key == record_key:
                return json.dumps(record)
            return None

        cache.get.side_effect = _get
        mock_cache_fn.return_value = cache

        result = validate(raw, expected_type='client')
        self.assertIsNotNone(result)
        self.assertEqual(result['user_id'], 'user-9')
        client.scan.assert_not_called()


class TestSessionExists(TestCase):

    @patch('core.auth.refresh_service._cache')
    def test_returns_true_when_key_exists(self, mock_cache_fn):
        cache = MagicMock()
        cache.get.return_value = '{"hash":"abc"}'
        mock_cache_fn.return_value = cache

        from core.auth.refresh_service import session_exists
        self.assertTrue(session_exists('client', 'user-1', 'abcdef1234567890'))
        cache.get.assert_called_once_with('rt:client:user-1:abcdef1234567890')

    @patch('core.auth.refresh_service._cache')
    def test_returns_false_when_key_missing(self, mock_cache_fn):
        cache = MagicMock()
        cache.get.return_value = None
        mock_cache_fn.return_value = cache

        from core.auth.refresh_service import session_exists
        self.assertFalse(session_exists('admin', 'user-2', 'deadbeef12345678'))

    @patch('core.auth.refresh_service._cache')
    def test_returns_false_after_revoke_by_session_key(self, mock_cache_fn):
        """After revoking via session key, session_exists must return False."""
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        # Simulate: first call returns data, second call (after delete) returns None
        cache.get.side_effect = ['{"hash":"abc"}', None]
        cache.delete.return_value = True

        from core.auth.refresh_service import session_exists, revoke_by_session_key

        self.assertTrue(session_exists('client', 'u1', 'tid1234567890ab'))
        revoke_by_session_key('rt:client:u1:tid1234567890ab')
        self.assertFalse(session_exists('client', 'u1', 'tid1234567890ab'))


class TestRevoke(TestCase):

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_revoke_returns_false_when_no_redis(self, mock_cache_fn, mock_redis):
        mock_redis.return_value = None

        from core.auth.refresh_service import revoke
        result = revoke('token', user_type='client')
        self.assertFalse(result)

    @patch('core.auth.refresh_service._get_redis_client')
    def test_revoke_all_returns_zero_when_no_redis(self, mock_redis):
        mock_redis.return_value = None

        from core.auth.refresh_service import revoke_all
        result = revoke_all()
        self.assertEqual(result, 0)


class TestRevokBySessionKey(TestCase):

    @patch('core.auth.refresh_service._cache')
    def test_revoke_by_session_key_delegates_to_cache_delete(self, mock_cache_fn):
        cache = MagicMock()
        cache.delete.return_value = True
        mock_cache_fn.return_value = cache

        from core.auth.refresh_service import revoke_by_session_key
        result = revoke_by_session_key('rt:client:user-1:abc123')
        # Borra el registro y también su índice inverso (rtid:type:token_id).
        cache.delete.assert_any_call('rt:client:user-1:abc123')
        cache.delete.assert_any_call('rtid:client:abc123')


class TestRevokeViaIndex(TestCase):

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_revoke_resolves_via_index_and_deletes_both(self, mock_cache_fn, mock_redis):
        """revoke() usa el índice inverso (sin SCAN) y borra registro + índice."""
        import json
        from core.auth.refresh_service import revoke, hash_token, _index_key

        client = MagicMock()
        mock_redis.return_value = client

        raw = 'raw-token-x'
        token_id = hash_token(raw)[:16]
        record_key = f'rt:client:u1:{token_id}'
        record = {'hash': hash_token(raw), 'user_id': 'u1', 'user_type': 'client'}

        cache = MagicMock()

        def _get(key):
            if key == _index_key('client', token_id):
                return record_key
            if key == record_key:
                return json.dumps(record)
            return None

        cache.get.side_effect = _get
        mock_cache_fn.return_value = cache

        result = revoke(raw, user_type='client')

        self.assertTrue(result)
        cache.delete.assert_any_call(record_key)
        cache.delete.assert_any_call(_index_key('client', token_id))
        client.scan.assert_not_called()


class TestRevokeAllForUserCleansIndexes(TestCase):

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_revoke_all_for_user_deletes_record_keys_and_indexes(self, mock_cache_fn, mock_redis):
        from core.auth.refresh_service import revoke_all_for_user, _index_key

        client = MagicMock()
        mock_redis.return_value = client
        client.scan.return_value = (
            0,
            [b'auth:1:rt:client:u1:tidAAA', b'auth:1:rt:client:u1:tidBBB'],
        )
        cache = MagicMock()
        mock_cache_fn.return_value = cache

        count = revoke_all_for_user('u1', 'client')

        self.assertEqual(count, 2)
        client.delete.assert_called_once()  # borra las claves de registro en bloque
        cache.delete.assert_any_call(_index_key('client', 'tidAAA'))
        cache.delete.assert_any_call(_index_key('client', 'tidBBB'))


class TestListLoadsPerKey(TestCase):

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_list_all_reads_each_key_safely(self, mock_cache_fn, mock_redis):
        """list_all() lee por clave (heal/drop corruptos); get_many abortaba el batch."""
        import json
        from core.auth.refresh_service import list_all

        client = MagicMock()
        mock_redis.return_value = client
        client.scan.return_value = (0, [b'auth:1:rt:client:u1:tid1'])

        cache = MagicMock()
        cache.get.return_value = json.dumps(
            {'hash': 'h', 'user_id': 'u1', 'user_type': 'client'},
        )
        mock_cache_fn.return_value = cache

        records = list_all()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['session_key'], 'rt:client:u1:tid1')
        cache.get.assert_called_once_with('rt:client:u1:tid1')
        cache.get_many.assert_not_called()


class TestStripPrefix(TestCase):

    def test_strips_auth_version_prefix(self):
        from core.auth.refresh_service import _strip_prefix
        # django-redis stores: auth:1:rt:admin:uuid:tid
        # _strip_prefix should return: rt:admin:uuid:tid
        self.assertEqual(_strip_prefix('auth:1:rt:admin:uuid:tid'), 'rt:admin:uuid:tid')

    def test_handles_bytes(self):
        from core.auth.refresh_service import _strip_prefix
        self.assertEqual(_strip_prefix(b'auth:1:rt:client:uuid:tid'), 'rt:client:uuid:tid')

    def test_passthrough_when_no_prefix(self):
        from core.auth.refresh_service import _strip_prefix
        self.assertEqual(_strip_prefix('rt:client:uuid:tid'), 'rt:client:uuid:tid')

    def test_redis_key_prefix_constant(self):
        from core.auth.refresh_service import _REDIS_KEY_PREFIX
        self.assertEqual(_REDIS_KEY_PREFIX, 'auth:1:')
