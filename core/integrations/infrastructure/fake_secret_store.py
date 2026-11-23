"""ISecretStore en memoria (tests)."""

from __future__ import annotations

from core.ids import uuid7
from core.integrations.domain.interfaces import ISecretStore


class FakeSecretStore(ISecretStore):

    def __init__(self):
        self._store: dict[str, dict[str, str]] = {}

    def put(self, scope: str, secrets: dict[str, str]) -> str:
        ref = f'{scope}:{uuid7()}'
        self._store[ref] = dict(secrets)
        return ref

    def get(self, ref: str) -> dict[str, str]:
        if ref not in self._store:
            raise KeyError(f'secret ref not found: {ref}')
        return dict(self._store[ref])

    def delete(self, ref: str) -> None:
        self._store.pop(ref, None)
