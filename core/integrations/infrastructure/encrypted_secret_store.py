"""Cifrado AES-GCM de secretos con clave maestra de plataforma."""

from __future__ import annotations

import hashlib
import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings

from core.ids import uuid7
from core.integrations.domain.interfaces import ISecretStore

logger = logging.getLogger('app.integrations')


def _derive_master_key(raw: str) -> bytes:
    return hashlib.sha256(raw.encode('utf-8')).digest()


class EncryptedSecretStore(ISecretStore):
    """
    Almacén en memoria con ciphertext AES-GCM.

    Fase 2 persiste ``ciphertext`` en BD tenant; esta clase encapsula
  el algoritmo de cifrado/descifrado.
    """

    def __init__(self, master_key: bytes | None = None):
        raw = getattr(settings, 'INTEGRATIONS_SECRET_KEY', '') or settings.SECRET_KEY
        key = master_key or _derive_master_key(raw)
        self._aesgcm = AESGCM(key)
        self._refs: dict[str, bytes] = {}

    def _encrypt(self, plaintext: bytes, associated_data: str) -> bytes:
        nonce = os.urandom(12)
        ad = associated_data.encode('utf-8') if associated_data else None
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, ad)
        return nonce + ciphertext

    def _decrypt(self, data: bytes, associated_data: str) -> bytes:
        nonce, ciphertext = data[:12], data[12:]
        ad = associated_data.encode('utf-8') if associated_data else None
        return self._aesgcm.decrypt(nonce, ciphertext, ad)

    def put(self, scope: str, secrets: dict[str, str]) -> str:
        import json

        payload = json.dumps(secrets, sort_keys=True).encode('utf-8')
        blob = self._encrypt(payload, scope)
        ref = f'{scope}:{uuid7()}'
        self._refs[ref] = blob
        return ref

    def get(self, ref: str) -> dict[str, str]:
        import json

        blob = self._refs.get(ref)
        if blob is None:
            raise KeyError(f'secret ref not found: {ref}')
        scope = ref.rsplit(':', 1)[0]
        payload = self._decrypt(blob, scope)
        return json.loads(payload.decode('utf-8'))

    def delete(self, ref: str) -> None:
        self._refs.pop(ref, None)
