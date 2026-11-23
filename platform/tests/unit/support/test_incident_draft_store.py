"""Unit tests de RedisIncidentDraftStore (SETEX/GETDEL, single-use)."""
import django
from django.conf import settings as dj_settings

if not dj_settings.configured:
    dj_settings._setup()  # pragma: no cover
django.setup()

import json
from unittest import TestCase
from unittest.mock import patch

from platform.features.support.incidents.incident.infrastructure import redis_draft_store
from platform.features.support.incidents.incident.infrastructure.redis_draft_store import (
    RedisIncidentDraftStore,
)


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.ttls = {}

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl

    def getdel(self, key):
        return self.store.pop(key, None)

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)


class RedisIncidentDraftStoreTests(TestCase):

    def setUp(self):
        self.fake = FakeRedis()
        self.patcher = patch.object(redis_draft_store, '_get_client', return_value=self.fake)
        self.patcher.start()
        self.store = RedisIncidentDraftStore()

    def tearDown(self):
        self.patcher.stop()

    def test_save_then_pop_roundtrip(self):
        self.store.save('tok', {'a': 1, 'error': {'code': 'SRV_001'}})
        self.assertEqual(self.fake.ttls['incident_draft:tok'], self.store._ttl)
        draft = self.store.pop('tok')
        self.assertEqual(draft, {'a': 1, 'error': {'code': 'SRV_001'}})

    def test_pop_is_single_use(self):
        self.store.save('tok', {'a': 1})
        self.assertIsNotNone(self.store.pop('tok'))
        self.assertIsNone(self.store.pop('tok'))  # segundo intento: ya consumido

    def test_pop_missing_returns_none(self):
        self.assertIsNone(self.store.pop('nope'))

    def test_empty_token_is_noop(self):
        self.store.save('', {'a': 1})
        self.assertEqual(self.fake.store, {})
        self.assertIsNone(self.store.pop(''))

    def test_survives_redis_failure(self):
        with patch.object(redis_draft_store, '_get_client', side_effect=RuntimeError('down')):
            self.store.save('tok', {'a': 1})       # no propaga
            self.assertIsNone(self.store.pop('tok'))

    def test_getdel_fallback_when_unavailable(self):
        # Cliente sin getdel: usa get + delete
        class OldRedis(FakeRedis):
            getdel = None
        old = OldRedis()
        old.store['incident_draft:tok'] = json.dumps({'x': 1})
        with patch.object(redis_draft_store, '_get_client', return_value=old):
            self.assertEqual(self.store.pop('tok'), {'x': 1})
            self.assertNotIn('incident_draft:tok', old.store)
