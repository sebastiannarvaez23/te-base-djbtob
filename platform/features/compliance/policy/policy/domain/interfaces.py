from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from .schemas import (
    CreatePolicySchema,
    PendingPolicySchema,
    PolicyCountrySummarySchema,
    PolicySchema,
    PolicySignatureSchema,
    SignatoryRef,
    UpdatePolicySchema,
)


class IPolicyRepository(ABC):

    @abstractmethod
    def list(self, filters: dict | None = None) -> List[PolicySchema]:
        ...

    @abstractmethod
    def get_by_id(self, policy_id: uuid.UUID) -> Optional[PolicySchema]:
        ...

    @abstractmethod
    def get_by_code(self, code: str) -> Optional[PolicySchema]:
        ...

    @abstractmethod
    def create(self, data: CreatePolicySchema) -> PolicySchema:
        ...

    @abstractmethod
    def update(self, policy_id: uuid.UUID, data: UpdatePolicySchema) -> Optional[PolicySchema]:
        ...

    @abstractmethod
    def delete(self, policy_id: uuid.UUID) -> bool:
        ...

    @abstractmethod
    def get_country(
        self, policy_id: uuid.UUID, country: str,
    ) -> Optional[PolicyCountrySummarySchema]:
        """Devuelve la versión **publicada** del país, si existe."""
        ...

    @abstractmethod
    def get_draft(
        self, policy_id: uuid.UUID, country: str,
    ) -> Optional[PolicyCountrySummarySchema]:
        ...

    @abstractmethod
    def get_approved(
        self, policy_id: uuid.UUID, country: str,
    ) -> Optional[PolicyCountrySummarySchema]:
        ...

    @abstractmethod
    def list_country_versions(
        self, policy_id: uuid.UUID, country: str,
    ) -> List[PolicyCountrySummarySchema]:
        """Historial (published/revoked/approved), newest first. Excluye drafts."""
        ...

    @abstractmethod
    def next_country_version(self, policy_id: uuid.UUID, country: str) -> int:
        """Siguiente versión (>=1); ignora drafts (version=0)."""
        ...

    @abstractmethod
    def create_draft(
        self,
        policy_id: uuid.UUID,
        *,
        country: str,
        title: str,
        object_key: str,
        content_hash: str,
        byte_size: int,
        geo_country_id: Optional[uuid.UUID] = None,
    ) -> PolicyCountrySummarySchema:
        ...

    @abstractmethod
    def update_draft(
        self,
        policy_id: uuid.UUID,
        country: str,
        *,
        title: str,
        content_hash: str,
        byte_size: int,
    ) -> Optional[PolicyCountrySummarySchema]:
        ...

    @abstractmethod
    def delete_draft(self, policy_id: uuid.UUID, country: str) -> Optional[PolicyCountrySummarySchema]:
        """Elimina el draft y devuelve su summary (para limpiar MinIO), o None."""
        ...

    @abstractmethod
    def create_approved_version(
        self,
        policy_id: uuid.UUID,
        *,
        country: str,
        version: int,
        title: str,
        object_key: str,
        content_hash: str,
        byte_size: int,
        change_summary: str = '',
    ) -> PolicyCountrySummarySchema:
        """Crea fila ``approved`` (versión materializada, aún no vigente)."""
        ...

    @abstractmethod
    def create_approved_version_and_drop_draft(
        self,
        policy_id: uuid.UUID,
        *,
        country: str,
        version: int,
        title: str,
        object_key: str,
        content_hash: str,
        byte_size: int,
        change_summary: str = '',
    ) -> tuple[PolicyCountrySummarySchema, Optional[PolicyCountrySummarySchema]]:
        """Atomic PG: insert approved + delete draft metadata."""
        ...

    @abstractmethod
    def release_approved_version(
        self,
        policy_id: uuid.UUID,
        country: str,
        *,
        revoke_reason: str = 'superseded',
    ) -> tuple[PolicyCountrySummarySchema, Optional[int]]:
        """
        Marca la fila approved como published y revoca la published previa.
        Devuelve (published_row, revoked_version_or_None).
        """
        ...

    @abstractmethod
    def delete_country(self, policy_id: uuid.UUID, country: str) -> bool:
        """Elimina todas las versiones del país si ninguna tiene firmas."""
        ...

    @abstractmethod
    def list_country_object_keys(self, policy_id: uuid.UUID) -> List[str]:
        ...


class IPolicySignatureRepository(ABC):

    @abstractmethod
    def create(self, data: PolicySignatureSchema) -> PolicySignatureSchema:
        ...

    @abstractmethod
    def get_by_id(self, signature_id: uuid.UUID) -> Optional[PolicySignatureSchema]:
        ...

    @abstractmethod
    def find_for_version(
        self,
        *,
        subject: SignatoryRef,
        policy_country_id: uuid.UUID,
        content_hash: str,
    ) -> Optional[PolicySignatureSchema]:
        ...

    @abstractmethod
    def list_for_policy(
        self, policy_id: uuid.UUID, filters: dict | None = None,
    ) -> List[PolicySignatureSchema]:
        ...

    @abstractmethod
    def list_pending_for_subject(
        self,
        *,
        subject: SignatoryRef,
        country: str,
        policy_codes: Sequence[str] | None = None,
    ) -> List[PendingPolicySchema]:
        """Pending published policies for subject/country.

        ``policy_codes``:
          - ``None`` → no code filter (all audience policies).
          - empty sequence → nothing pending.
          - non-empty → only those codes.
        """
        ...
