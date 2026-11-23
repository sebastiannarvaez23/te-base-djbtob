"""TIME_INACTIVITY: idle window, refresh carry, and session rejection."""
from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch

from core.auth.inactivity import (
    carried_last_activity,
    clear_inactivity_cache,
    inactivity_minutes,
    reject_idle_admin_session,
    reject_idle_client_session,
    session_record_is_idle,
)


class TestInactivityWindow(TestCase):

    def setUp(self):
        clear_inactivity_cache()

    def tearDown(self):
        clear_inactivity_cache()

    @patch('core.parameters.get_parameter', return_value=0)
    def test_zero_disables(self, _param):
        self.assertEqual(inactivity_minutes(), 0)
        self.assertFalse(session_record_is_idle({'last_activity_at': '2000-01-01T00:00:00'}))

    @patch('core.parameters.get_parameter', return_value='15')
    def test_minutes_become_seconds(self, _param):
        self.assertEqual(inactivity_minutes(), 15)

    @patch('core.admin_parameters.get_admin_parameter', return_value='20')
    def test_admin_catalog_minutes(self, _param):
        self.assertEqual(inactivity_minutes(user_type='admin'), 20)

    @patch('core.parameters.get_parameter', return_value='nope')
    def test_invalid_value_disables(self, _param):
        self.assertEqual(inactivity_minutes(), 0)

    @patch('core.parameters.get_parameter', return_value=15)
    def test_legacy_record_without_activity_is_not_idle(self, _param):
        self.assertFalse(session_record_is_idle({'created_at': '2000-01-01T00:00:00'}))

    @patch('core.parameters.get_parameter', return_value=15)
    def test_recent_activity_is_not_idle(self, _param):
        recent = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
        self.assertFalse(session_record_is_idle({'last_activity_at': recent}))

    @patch('core.parameters.get_parameter', return_value=15)
    def test_quiet_record_is_idle(self, _param):
        quiet = (datetime.utcnow() - timedelta(minutes=16)).isoformat()
        self.assertTrue(session_record_is_idle({'last_activity_at': quiet}))

    @patch('core.parameters.get_parameter', return_value=0)
    @patch('core.admin_parameters.get_admin_parameter', return_value=10)
    def test_admin_idle_uses_admin_catalog_not_client(self, _admin_param, _client_param):
        quiet = (datetime.utcnow() - timedelta(minutes=12)).isoformat()
        self.assertTrue(
            session_record_is_idle({'last_activity_at': quiet}, user_type='admin'),
        )
        self.assertFalse(
            session_record_is_idle({'last_activity_at': quiet}, user_type='client'),
        )

    def test_carried_activity_keeps_previous_timestamp(self):
        self.assertEqual(
            carried_last_activity({'last_activity_at': '2026-01-01T00:00:00'}),
            '2026-01-01T00:00:00',
        )
        self.assertIsNone(carried_last_activity({'created_at': '2026-01-01T00:00:00'}))
        self.assertIsNone(carried_last_activity(None))


class TestRejectIdleAdminSession(TestCase):

    def setUp(self):
        clear_inactivity_cache()

    def tearDown(self):
        clear_inactivity_cache()

    @patch('core.auth.refresh_service.revoke_session')
    @patch('core.auth.refresh_service.read_session')
    @patch('core.admin_parameters.get_admin_parameter', return_value=15)
    def test_idle_admin_session_is_revoked(self, _param, read, revoke):
        read.return_value = {
            'last_activity_at': (datetime.utcnow() - timedelta(minutes=20)).isoformat(),
        }
        self.assertTrue(reject_idle_admin_session('admin-1', 'sid-1'))
        revoke.assert_called_once_with('admin', 'admin-1', 'sid-1')

    @patch('core.auth.refresh_service.touch_session_activity')
    @patch('core.auth.refresh_service.read_session')
    @patch('core.admin_parameters.get_admin_parameter', return_value=15)
    def test_live_admin_session_is_touched(self, _param, read, touch):
        record = {'last_activity_at': datetime.utcnow().isoformat()}
        read.return_value = record
        self.assertFalse(reject_idle_admin_session('admin-1', 'sid-1'))
        touch.assert_called_once_with('admin', 'admin-1', 'sid-1', record)


class TestRejectIdleClientSession(TestCase):

    def setUp(self):
        clear_inactivity_cache()

    def tearDown(self):
        clear_inactivity_cache()

    @patch('core.auth.refresh_service.touch_session_activity')
    @patch('core.auth.refresh_service.read_session')
    @patch('core.parameters.get_parameter', return_value=0)
    def test_disabled_policy_still_slides_activity(self, _param, read, touch):
        record = {'last_activity_at': datetime.utcnow().isoformat()}
        read.return_value = record
        self.assertFalse(reject_idle_client_session('user-1', 'sid-1'))
        touch.assert_called_once_with('client', 'user-1', 'sid-1', record)

    @patch('core.auth.refresh_service.touch_session_activity')
    @patch('core.auth.refresh_service.read_session', return_value=None)
    @patch('core.parameters.get_parameter', return_value=15)
    def test_missing_record_is_not_idle(self, _param, _read, touch):
        self.assertFalse(reject_idle_client_session('user-1', 'sid-1'))
        touch.assert_not_called()

    @patch('core.auth.refresh_service.revoke_session')
    @patch('core.auth.refresh_service.read_session')
    @patch('core.parameters.get_parameter', return_value=15)
    def test_idle_session_is_revoked(self, _param, read, revoke):
        read.return_value = {
            'last_activity_at': (datetime.utcnow() - timedelta(minutes=20)).isoformat(),
        }
        self.assertTrue(reject_idle_client_session('user-1', 'sid-1'))
        revoke.assert_called_once_with('client', 'user-1', 'sid-1')

    @patch('core.auth.refresh_service.touch_session_activity')
    @patch('core.auth.refresh_service.read_session')
    @patch('core.parameters.get_parameter', return_value=15)
    def test_live_session_is_touched(self, _param, read, touch):
        record = {'last_activity_at': datetime.utcnow().isoformat()}
        read.return_value = record
        self.assertFalse(reject_idle_client_session('user-1', 'sid-1'))
        touch.assert_called_once_with('client', 'user-1', 'sid-1', record)

    @patch('core.auth.refresh_service.touch_session_activity')
    @patch('core.auth.refresh_service.read_session')
    @patch('core.parameters.get_parameter', return_value=15)
    def test_reuses_passed_record_without_extra_read(self, _param, read, touch):
        record = {'last_activity_at': datetime.utcnow().isoformat()}
        self.assertFalse(reject_idle_client_session('user-1', 'sid-1', record=record))
        read.assert_not_called()
        touch.assert_called_once_with('client', 'user-1', 'sid-1', record)


class TestTouchSessionActivity(TestCase):

    @patch('core.auth.refresh_service._set_existing_record', return_value=True)
    @patch('core.auth.refresh_service._remaining_ttl', return_value=3600)
    @patch('core.auth.refresh_service._cache')
    def test_writes_when_activity_is_stale(self, mock_cache_fn, _ttl, set_xx):
        from core.auth.refresh_service import touch_session_activity

        mock_cache_fn.return_value = MagicMock()
        stale = (datetime.utcnow() - timedelta(seconds=60)).isoformat()
        record = {'hash': 'abc', 'last_activity_at': stale}
        self.assertTrue(touch_session_activity('client', 'u1', 'sid', record))
        set_xx.assert_called_once()
        written = set_xx.call_args.args[1]
        self.assertEqual(written['hash'], 'abc')
        self.assertNotEqual(written['last_activity_at'], stale)

    @patch('core.auth.refresh_service._set_existing_record')
    @patch('core.auth.refresh_service._remaining_ttl', return_value=3600)
    @patch('core.auth.refresh_service._cache')
    def test_throttles_recent_activity(self, mock_cache_fn, _ttl, set_xx):
        from core.auth.refresh_service import touch_session_activity

        mock_cache_fn.return_value = MagicMock()
        recent = datetime.utcnow().isoformat()
        self.assertFalse(
            touch_session_activity('client', 'u1', 'sid', {'last_activity_at': recent}),
        )
        set_xx.assert_not_called()

    @patch('core.auth.refresh_service._set_existing_record')
    @patch('core.auth.refresh_service._remaining_ttl', return_value=None)
    @patch('core.auth.refresh_service._cache')
    def test_skips_when_key_missing(self, mock_cache_fn, _ttl, set_xx):
        from core.auth.refresh_service import touch_session_activity

        mock_cache_fn.return_value = MagicMock()
        stale = (datetime.utcnow() - timedelta(seconds=60)).isoformat()
        self.assertFalse(
            touch_session_activity('client', 'u1', 'sid', {'last_activity_at': stale}),
        )
        set_xx.assert_not_called()

    @patch('core.auth.refresh_service._cache')
    @patch('core.auth.refresh_service._get_redis_client')
    def test_set_existing_uses_xx_with_django_encoding(self, mock_redis, mock_cache_fn):
        from core.auth.refresh_service import _set_existing_record

        client = MagicMock()
        client.set.return_value = True
        mock_redis.return_value = client
        redis_client = MagicMock()
        redis_client.make_key.return_value = 'auth:1:rt:client:u1:sid'
        redis_client.encode.return_value = b'pickled'
        mock_cache_fn.return_value.client = redis_client

        self.assertTrue(_set_existing_record('rt:client:u1:sid', {'a': 1}, 120))
        redis_client.encode.assert_called_once()
        kwargs = client.set.call_args.kwargs
        self.assertTrue(kwargs.get('xx'))
        self.assertEqual(kwargs.get('ex'), 120)
        self.assertEqual(client.set.call_args.args[1], b'pickled')

    @patch('core.auth.refresh_service._cache')
    @patch('core.auth.refresh_service._get_redis_client')
    def test_set_existing_does_not_resurrect(self, mock_redis, mock_cache_fn):
        from core.auth.refresh_service import _set_existing_record

        client = MagicMock()
        client.set.return_value = None  # XX miss
        mock_redis.return_value = client
        redis_client = MagicMock()
        redis_client.make_key.return_value = 'auth:1:rt:client:u1:sid'
        redis_client.encode.return_value = b'pickled'
        mock_cache_fn.return_value.client = redis_client
        self.assertFalse(_set_existing_record('rt:client:u1:sid', {'a': 1}, 120))

    @patch('core.auth.refresh_service._drop_corrupt_session_key')
    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_read_record_heals_raw_json(self, mock_cache_fn, mock_redis, drop):
        import json
        from core.auth.refresh_service import _read_record

        cache = MagicMock()
        cache.get.side_effect = Exception('UnpicklingError')
        cache.set = MagicMock()
        mock_cache_fn.return_value = cache
        client = MagicMock()
        payload = {'hash': 'abc', 'user_id': 'u1', 'last_activity_at': '2026-01-01T00:00:00'}
        client.get.return_value = json.dumps(payload).encode()
        client.ttl.return_value = 600
        mock_redis.return_value = client

        with patch('core.auth.refresh_service._remaining_ttl', return_value=600):
            record = _read_record(cache, 'rt:client:u1:sid')
        self.assertEqual(record['hash'], 'abc')
        cache.set.assert_called_once()
        drop.assert_not_called()


class TestRefreshStoreKeepsActivity(TestCase):

    @patch('core.auth.refresh_service._get_redis_client')
    @patch('core.auth.refresh_service._cache')
    def test_store_copies_last_activity(self, mock_cache_fn, _redis):
        import json
        cache = MagicMock()
        mock_cache_fn.return_value = cache
        from core.auth.refresh_service import store

        store(
            raw_token='raw-token',
            user_id='user-1',
            user_type='client',
            ttl_seconds=3600,
            remember_me=True,
            last_activity_at='2026-01-01T00:00:00',
        )
        record_call = next(
            call for call in cache.set.call_args_list
            if call.args[0].startswith('rt:client:')
        )
        payload = json.loads(record_call.args[1])
        self.assertEqual(payload['last_activity_at'], '2026-01-01T00:00:00')
