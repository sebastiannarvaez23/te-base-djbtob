"""Matriz escenarios 9–10 — Secret stores."""

import pytest
from cryptography.exceptions import InvalidTag

from core.integrations.infrastructure.encrypted_secret_store import EncryptedSecretStore
from core.integrations.infrastructure.fake_secret_store import FakeSecretStore


@pytest.mark.unit
class TestSecretStore:

    def test_fake_round_trip(self):
        store = FakeSecretStore()
        ref = store.put('tenant:conn', {'api_key': 'abc'})
        assert store.get(ref)['api_key'] == 'abc'

    def test_encrypted_round_trip(self):
        store = EncryptedSecretStore(master_key=b'0' * 32)
        ref = store.put('tenant:conn', {'password': 's3cr3t'})
        assert store.get(ref)['password'] == 's3cr3t'

    def test_wrong_master_key_fails_controlled(self):
        store = EncryptedSecretStore(master_key=b'1' * 32)
        ref = store.put('tenant:conn', {'token': 'x'})
        bad = EncryptedSecretStore(master_key=b'2' * 32)
        with pytest.raises((InvalidTag, Exception)):
            bad.get(ref)
