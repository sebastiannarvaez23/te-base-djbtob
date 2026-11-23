"""Persistencia BYOK: ciphertext AES-GCM reutilizando EncryptedSecretStore."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.errors import AppErrorCode, ConflictException, NotFoundException, ValidationAppException
from core.integrations.infrastructure.encrypted_secret_store import EncryptedSecretStore

from client.features.communication.assistant.credentials.domain.interfaces import (
    IAssistantCredentialRepository,
)
from client.features.communication.assistant.credentials.domain.schemas import (
    ActiveByokSchema,
    CreateCredentialSchema,
    CredentialPublicSchema,
    UpdateCredentialSchema,
)
from client.features.communication.assistant.credentials.models import (
    AssistantProviderCredential,
)

logger = logging.getLogger('app.ai')

_ALLOWED = frozenset({'openai', 'anthropic'})


def _last4(api_key: str) -> str:
    cleaned = (api_key or '').strip()
    return cleaned[-4:] if len(cleaned) >= 4 else cleaned


def _to_public(row: AssistantProviderCredential) -> CredentialPublicSchema:
    return CredentialPublicSchema(
        id=row.id,
        provider=row.provider,
        label=row.label or '',
        key_last4=row.key_last4 or '',
        is_active=bool(row.is_active),
        last_validated_at=row.last_validated_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class DjangoAssistantCredentialRepository(IAssistantCredentialRepository):
    """Thin ORM adapter — business rules live in application use cases."""

    def __init__(self, store: EncryptedSecretStore | None = None):
        self._crypto = store or EncryptedSecretStore()

    def _enc_scope(self, credential_id: uuid.UUID) -> str:
        return f'assistant-byok:{credential_id}'

    def _encrypt_key(self, credential_id: uuid.UUID, api_key: str) -> bytes:
        payload = json.dumps({'api_key': api_key}, sort_keys=True).encode('utf-8')
        return self._crypto._encrypt(payload, self._enc_scope(credential_id))

    def _decrypt_key(self, row: AssistantProviderCredential) -> str:
        payload = self._crypto._decrypt(bytes(row.ciphertext), self._enc_scope(row.id))
        data = json.loads(payload.decode('utf-8'))
        return str(data.get('api_key') or '')

    def list_public(self) -> list[CredentialPublicSchema]:
        rows = AssistantProviderCredential.objects.all().order_by('-updated_at')
        return [_to_public(r) for r in rows]

    def _deactivate_others(self, provider: str, keep_id: uuid.UUID) -> None:
        AssistantProviderCredential.objects.select_for_update().filter(
            provider=provider, is_active=True,
        ).exclude(id=keep_id).update(is_active=False)

    @transaction.atomic
    def create(self, schema: CreateCredentialSchema) -> CredentialPublicSchema:
        provider = (schema.provider or '').strip().lower()
        if provider not in _ALLOWED:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='Provider must be openai or anthropic.',
            )
        api_key = (schema.api_key or '').strip()
        if len(api_key) < 8:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='API key is too short.',
            )

        # Encrypt with a temporary id scope after first save (needs PK).
        row = AssistantProviderCredential(
            provider=provider,
            label=(schema.label or '').strip()[:120],
            ciphertext=b'\x00',  # placeholder — replaced before commit
            key_last4=_last4(api_key),
            is_active=False,
            created_by=schema.created_by,
            last_validated_at=None,
        )
        try:
            row.save()
            row.ciphertext = self._encrypt_key(row.id, api_key)
            if schema.activate:
                self._deactivate_others(provider, row.id)
                row.is_active = True
            # Do NOT set last_validated_at — requires a real provider probe.
            row.save(update_fields=['ciphertext', 'is_active', 'updated_at'])
        except IntegrityError as exc:
            raise ConflictException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='Another active credential already exists for this provider.',
            ) from exc
        return _to_public(row)

    @transaction.atomic
    def update(
        self,
        credential_id: uuid.UUID,
        schema: UpdateCredentialSchema,
    ) -> CredentialPublicSchema:
        row = (
            AssistantProviderCredential.objects.select_for_update()
            .filter(id=credential_id)
            .first()
        )
        if row is None:
            raise NotFoundException(AppErrorCode.AI_CREDENTIAL_NOT_FOUND)

        fields: list[str] = ['updated_at']
        if schema.label is not None:
            row.label = schema.label.strip()[:120]
            fields.append('label')
        if schema.api_key is not None:
            api_key = schema.api_key.strip()
            if len(api_key) < 8:
                raise ValidationAppException(
                    AppErrorCode.VALIDATION_ERROR,
                    override_detail='API key is too short.',
                )
            row.ciphertext = self._encrypt_key(row.id, api_key)
            row.key_last4 = _last4(api_key)
            # Key rotated — clear prior "validated" stamp until a probe exists.
            row.last_validated_at = None
            fields.extend(['ciphertext', 'key_last4', 'last_validated_at'])
        if schema.is_active is not None:
            if schema.is_active:
                try:
                    self._deactivate_others(row.provider, row.id)
                except IntegrityError as exc:
                    raise ConflictException(
                        AppErrorCode.VALIDATION_ERROR,
                        override_detail=(
                            'Another active credential already exists for this provider.'
                        ),
                    ) from exc
            row.is_active = bool(schema.is_active)
            fields.append('is_active')
        try:
            row.save(update_fields=list(dict.fromkeys(fields)))
        except IntegrityError as exc:
            raise ConflictException(
                AppErrorCode.VALIDATION_ERROR,
                override_detail='Another active credential already exists for this provider.',
            ) from exc
        return _to_public(row)

    def delete(self, credential_id: uuid.UUID) -> None:
        deleted, _ = AssistantProviderCredential.objects.filter(id=credential_id).delete()
        if not deleted:
            raise NotFoundException(AppErrorCode.AI_CREDENTIAL_NOT_FOUND)

    def get_active_byok(self, provider: str | None = None) -> Optional[ActiveByokSchema]:
        """Requires ``provider`` to avoid ambiguous multi-active selection."""
        if not provider:
            return None
        qs = AssistantProviderCredential.objects.filter(
            is_active=True,
            provider=provider.lower().strip(),
        )
        row = qs.order_by('-updated_at').first()
        if row is None:
            return None
        try:
            api_key = self._decrypt_key(row)
        except Exception as exc:
            logger.warning('BYOK decrypt failed for %s: %s', row.id, exc)
            return None
        if not api_key:
            return None
        return ActiveByokSchema(
            provider=row.provider,
            api_key=api_key,
            credential_id=row.id,
        )

    def mark_validated(self, credential_id: uuid.UUID) -> None:
        """Set last_validated_at after a successful provider probe."""
        AssistantProviderCredential.objects.filter(id=credential_id).update(
            last_validated_at=timezone.now(),
        )
