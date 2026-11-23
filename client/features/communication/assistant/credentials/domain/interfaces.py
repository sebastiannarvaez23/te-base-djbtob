from __future__ import annotations

import abc
import uuid
from typing import Optional

from .schemas import (
    ActiveByokSchema,
    CreateCredentialSchema,
    CredentialPublicSchema,
    UpdateCredentialSchema,
)


class IAssistantCredentialRepository(abc.ABC):

    @abc.abstractmethod
    def list_public(self) -> list[CredentialPublicSchema]:
        ...

    @abc.abstractmethod
    def create(self, schema: CreateCredentialSchema) -> CredentialPublicSchema:
        ...

    @abc.abstractmethod
    def update(
        self,
        credential_id: uuid.UUID,
        schema: UpdateCredentialSchema,
    ) -> CredentialPublicSchema:
        ...

    @abc.abstractmethod
    def delete(self, credential_id: uuid.UUID) -> None:
        ...

    @abc.abstractmethod
    def get_active_byok(self, provider: str | None = None) -> Optional[ActiveByokSchema]:
        """Active BYOK for a specific provider (provider required to avoid ambiguity)."""
        ...

    def mark_validated(self, credential_id: uuid.UUID) -> None:
        """Optional: stamp last_validated_at after a live provider probe."""
        return None
