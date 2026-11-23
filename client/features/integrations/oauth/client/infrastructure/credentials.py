"""CSPRNG-backed credential factory for Integration Applications.

Secrets carry 288 bits of entropy, so a single SHA-256 digest is enough to
make offline guessing infeasible; a slow KDF would only add latency to every
token request. Digests from the previous Django-hasher scheme still verify.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from django.contrib.auth.hashers import check_password

from client.features.integrations.oauth.client.domain.interfaces import ICredentialFactory
from client.features.integrations.oauth.client.domain.schemas import GeneratedSecretSchema

CLIENT_ID_PREFIX = 'wa_'
_CLIENT_ID_BYTES = 18
_CLIENT_SECRET_BYTES = 36
_SECRET_PREFIX_LEN = 8
_DIGEST_SCHEME = 'sha256$'


def _digest(raw_secret: str) -> str:
    return _DIGEST_SCHEME + hashlib.sha256(raw_secret.encode('utf-8')).hexdigest()


class SecureCredentialFactory(ICredentialFactory):

    def new_client_id(self) -> str:
        return f'{CLIENT_ID_PREFIX}{secrets.token_urlsafe(_CLIENT_ID_BYTES)}'

    def new_secret(self) -> GeneratedSecretSchema:
        raw = secrets.token_urlsafe(_CLIENT_SECRET_BYTES)
        return GeneratedSecretSchema(
            raw=raw,
            digest=_digest(raw),
            prefix=raw[:_SECRET_PREFIX_LEN],
        )

    def verify_secret(self, raw_secret: str, digest: str) -> bool:
        if not raw_secret or not digest:
            return False
        if digest.startswith(_DIGEST_SCHEME):
            return hmac.compare_digest(_digest(raw_secret), digest)
        return check_password(raw_secret, digest)
