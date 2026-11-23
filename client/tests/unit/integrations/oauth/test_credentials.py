"""Unit tests — SecureCredentialFactory (client id / secret minting)."""

import pytest
from django.contrib.auth.hashers import make_password

from client.features.integrations.oauth.client.domain.interfaces import ICredentialFactory
from client.features.integrations.oauth.client.infrastructure.credentials import (
    CLIENT_ID_PREFIX,
    SecureCredentialFactory,
)


@pytest.fixture
def factory():
    return SecureCredentialFactory()


@pytest.mark.unit
class TestSecureCredentialFactory:

    def test_implements_port(self, factory):
        assert isinstance(factory, ICredentialFactory)

    def test_client_id_has_prefix_and_entropy(self, factory):
        cid = factory.new_client_id()
        assert cid.startswith(CLIENT_ID_PREFIX)
        assert len(cid) <= 64
        assert len(cid) - len(CLIENT_ID_PREFIX) >= 24

    def test_client_ids_are_unique(self, factory):
        assert len({factory.new_client_id() for _ in range(50)}) == 50

    def test_secret_shape(self, factory):
        secret = factory.new_secret()
        assert len(secret.raw) >= 48
        assert secret.prefix == secret.raw[:8]
        assert secret.digest.startswith('sha256$')
        assert secret.raw not in secret.digest
        assert len(secret.digest) <= 128

    def test_secrets_are_unique(self, factory):
        assert len({factory.new_secret().raw for _ in range(50)}) == 50

    def test_raw_secret_hidden_from_repr(self, factory):
        secret = factory.new_secret()
        assert secret.raw not in repr(secret)
        assert secret.digest not in repr(secret)

    def test_verify_round_trip(self, factory):
        secret = factory.new_secret()
        assert factory.verify_secret(secret.raw, secret.digest) is True
        assert factory.verify_secret(secret.raw + 'x', secret.digest) is False

    def test_verify_rejects_empty(self, factory):
        assert factory.verify_secret('', 'sha256$abc') is False
        assert factory.verify_secret('x', '') is False

    def test_verify_accepts_legacy_django_digest(self, factory):
        legacy = make_password('legacy-secret-value-0123456789')
        assert factory.verify_secret('legacy-secret-value-0123456789', legacy) is True
        assert factory.verify_secret('other', legacy) is False
