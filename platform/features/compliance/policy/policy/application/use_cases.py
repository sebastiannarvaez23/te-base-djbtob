"""Casos de uso de gestión de políticas (metadata PG + markdown MinIO)."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import List, Optional

from core.errors import (
    AppErrorCode,
    ConflictException,
    NotFoundException,
    ServerException,
    ValidationAppException,
)
from core.signing import hash_content
from core.storage import (
    EnsureBucketUseCase,
    IStorageService,
    UploadFileSchema,
)


from ..domain.enums import PolicyCountryStatus
from ..domain.interfaces import IPolicyRepository
from ..domain.paths import (
    POLICY_BUCKET,
    POLICY_MARKDOWN_CONTENT_TYPE,
    policy_draft_object_key,
    policy_object_key,
)
from ..domain.schemas import (
    CreatePolicySchema,
    PolicyCountryContentSchema,
    PolicyCountrySummarySchema,
    PolicySchema,
    PublishPolicyCountryResultSchema,
    ReleasePolicyCountryDraftSchema,
    SavePolicyCountryDraftSchema,
    UpdatePolicySchema,
)
from core.trace import trace_layer

logger = logging.getLogger('app.api')


def _draft_digest(raw: bytes) -> str:
    """SHA-256 del markdown del borrador (permite vacío; firmas no)."""
    return hashlib.sha256(raw).hexdigest()


def _ensure_bucket(storage: IStorageService) -> None:
    EnsureBucketUseCase(storage).execute(POLICY_BUCKET)


def _upload_markdown(
    storage: IStorageService,
    *,
    object_key: str,
    raw: bytes,
    metadata: dict,
    overwrite: bool = False,
) -> None:
    _ensure_bucket(storage)
    if not overwrite and storage.file_exists(POLICY_BUCKET, object_key):
        raise ServerException(
            AppErrorCode.POLICY_STORAGE_ERROR,
            context={
                'object_key': object_key,
                'error': 'versioned object key already exists',
            },
        )
    upload = UploadFileSchema(
        bucket=POLICY_BUCKET,
        object_name=object_key,
        data=raw,
        content_type=POLICY_MARKDOWN_CONTENT_TYPE,
        metadata=metadata,
    )
    try:
        storage.upload_file(upload)
    except ServerException:
        raise
    except Exception as exc:
        logger.exception('Policy markdown storage failed for %s', object_key)
        raise ServerException(
            AppErrorCode.POLICY_STORAGE_ERROR,
            context={'object_key': object_key, 'error': str(exc)},
        ) from exc


def _download_markdown(storage: IStorageService, object_key: str) -> bytes:
    try:
        return storage.download_file(POLICY_BUCKET, object_key)
    except Exception as exc:
        logger.exception('Failed to download policy %s', object_key)
        raise ServerException(
            AppErrorCode.POLICY_STORAGE_ERROR,
            context={'object_key': object_key, 'error': str(exc)},
        ) from exc


def _normalize_country_param(country: str) -> str:
    from ..domain.schemas import normalize_country

    try:
        return normalize_country(country)
    except ValueError as exc:
        raise ValidationAppException(
            AppErrorCode.POLICY_INVALID_COUNTRY,
            override_detail=str(exc),
        ) from exc


def _require_geo_country(country_code: str):
    """Resuelve el país en la maestra de locaciones (activo)."""
    from platform.features.geography.location.location.models import Country

    try:
        row = Country.objects.only('id', 'is_active').get(code=country_code.strip().upper())
    except Country.DoesNotExist as exc:
        raise ValidationAppException(AppErrorCode.GEO_COUNTRY_NOT_FOUND) from exc
    if not row.is_active:
        raise ValidationAppException(AppErrorCode.GEO_COUNTRY_INACTIVE)
    return row


class ListPoliciesUseCase:
    def __init__(self, repository: IPolicyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, filters: dict | None = None) -> List[PolicySchema]:
        return self.repository.list(filters=filters)


class GetPolicyByIdUseCase:
    def __init__(self, repository: IPolicyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID) -> PolicySchema:
        policy = self.repository.get_by_id(policy_id)
        if not policy:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        return policy


class CreatePolicyUseCase:
    def __init__(self, repository: IPolicyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, data: CreatePolicySchema) -> PolicySchema:
        existing = self.repository.get_by_code(data.code)
        if existing:
            raise ConflictException(AppErrorCode.POLICY_DUPLICATE_CODE)
        return self.repository.create(data)


class UpdatePolicyUseCase:
    def __init__(self, repository: IPolicyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID, data: UpdatePolicySchema) -> PolicySchema:
        if not self.repository.get_by_id(policy_id):
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        updated = self.repository.update(policy_id, data)
        if not updated:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        return updated


class DeletePolicyUseCase:
    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID) -> None:
        keys = self.repository.list_country_object_keys(policy_id)
        deleted = self.repository.delete(policy_id)
        if not deleted:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        for key in keys:
            try:
                self.storage.delete_file(POLICY_BUCKET, key)
            except Exception:
                logger.exception('Failed to delete policy object %s/%s', POLICY_BUCKET, key)


class StartPolicyCountryDraftUseCase:
    """Crea o reabre el borrador de un país (copia published si existe)."""

    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID, country: str) -> PolicyCountryContentSchema:
        country = _normalize_country_param(country)
        policy = self.repository.get_by_id(policy_id)
        if not policy:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)

        existing = self.repository.get_draft(policy_id, country)
        if existing:
            raw = _download_markdown(self.storage, existing.object_key)
            return PolicyCountryContentSchema(
                policy_id=policy.id,
                policy_code=policy.code,
                audience=policy.audience,
                country=existing.country,
                version=existing.version,
                status=existing.status,
                title=existing.title,
                markdown=raw.decode('utf-8'),
                object_key=existing.object_key,
                content_hash=existing.content_hash,
                byte_size=existing.byte_size,
                change_summary=existing.change_summary or '',
                updated_at=existing.updated_at,
            )

        published = self.repository.get_country(policy_id, country)
        title = published.title if published else policy.name
        markdown = ''
        if published:
            markdown = _download_markdown(self.storage, published.object_key).decode('utf-8')

        geo_country = _require_geo_country(country)

        raw = markdown.encode('utf-8')
        digest = _draft_digest(raw)
        object_key = policy_draft_object_key(policy.audience, policy.code, country)
        _upload_markdown(
            self.storage,
            object_key=object_key,
            raw=raw,
            metadata={
                'policy_id': str(policy.id),
                'policy_code': policy.code,
                'country': country,
                'status': 'draft',
                'content_hash': digest,
            },
            overwrite=True,
        )
        draft = self.repository.create_draft(
            policy_id,
            country=country,
            title=title,
            object_key=object_key,
            content_hash=digest,
            byte_size=len(raw),
            geo_country_id=geo_country.id,
        )
        return PolicyCountryContentSchema(
            policy_id=policy.id,
            policy_code=policy.code,
            audience=policy.audience,
            country=draft.country,
            version=draft.version,
            status=draft.status,
            title=draft.title,
            markdown=markdown,
            object_key=draft.object_key,
            content_hash=draft.content_hash,
            byte_size=draft.byte_size,
            change_summary='',
            updated_at=draft.updated_at,
        )


class SavePolicyCountryDraftUseCase:
    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(
        self, policy_id: uuid.UUID, country: str, data: SavePolicyCountryDraftSchema,
    ) -> PolicyCountrySummarySchema:
        country = _normalize_country_param(country)
        policy = self.repository.get_by_id(policy_id)
        if not policy:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)

        draft = self.repository.get_draft(policy_id, country)
        if not draft:
            raise NotFoundException(AppErrorCode.POLICY_DRAFT_NOT_FOUND)

        raw = (data.markdown or '').encode('utf-8')
        digest = _draft_digest(raw)
        _upload_markdown(
            self.storage,
            object_key=draft.object_key,
            raw=raw,
            metadata={
                'policy_id': str(policy.id),
                'policy_code': policy.code,
                'country': country,
                'status': 'draft',
                'content_hash': digest,
            },
            overwrite=True,
        )
        updated = self.repository.update_draft(
            policy_id,
            country,
            title=data.title,
            content_hash=digest,
            byte_size=len(raw),
        )
        if not updated:
            raise NotFoundException(AppErrorCode.POLICY_DRAFT_NOT_FOUND)
        return updated


class ApprovePolicyCountryDraftUseCase:
    """
    Materializa el borrador como versión ``approved`` (vN.md) y elimina el draft.
    No hace vigente la versión (eso es Release).
    """

    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(
        self,
        policy_id: uuid.UUID,
        country: str,
        *,
        change_summary: str = '',
    ) -> PolicyCountrySummarySchema:
        country = _normalize_country_param(country)
        policy = self.repository.get_by_id(policy_id)
        if not policy:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)

        draft = self.repository.get_draft(policy_id, country)
        if not draft:
            raise NotFoundException(AppErrorCode.POLICY_DRAFT_NOT_FOUND)

        raw = _download_markdown(self.storage, draft.object_key)
        if not raw.decode('utf-8').strip():
            raise ValidationAppException(AppErrorCode.POLICY_EMPTY_MARKDOWN)

        if _draft_digest(raw) != draft.content_hash:
            raise ConflictException(AppErrorCode.POLICY_CONTENT_TAMPERED)
        digest = hash_content(raw)

        next_version = self.repository.next_country_version(policy_id, country)
        object_key = policy_object_key(
            policy.audience, policy.code, country, next_version,
        )
        uploaded = False
        try:
            _upload_markdown(
                self.storage,
                object_key=object_key,
                raw=raw,
                metadata={
                    'policy_id': str(policy.id),
                    'policy_code': policy.code,
                    'country': country,
                    'version': str(next_version),
                    'content_hash': digest,
                },
                overwrite=False,
            )
            uploaded = True

            approved, deleted = self.repository.create_approved_version_and_drop_draft(
                policy_id,
                country=country,
                version=next_version,
                title=draft.title,
                object_key=object_key,
                content_hash=digest,
                byte_size=len(raw),
                change_summary=(change_summary or '').strip(),
            )
        except Exception:
            if uploaded:
                try:
                    self.storage.delete_file(POLICY_BUCKET, object_key)
                except Exception:
                    logger.exception(
                        'Failed to compensate orphan policy object %s', object_key,
                    )
            raise

        if deleted:
            try:
                self.storage.delete_file(POLICY_BUCKET, deleted.object_key)
            except Exception:
                logger.exception('Failed to delete draft object %s', deleted.object_key)
        return approved


class ReleasePolicyCountryVersionUseCase:
    """Pasa la fila ``approved`` a ``published`` y revoca la published previa."""

    def __init__(self, repository: IPolicyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(
        self, policy_id: uuid.UUID, country: str,
    ) -> tuple[PolicyCountrySummarySchema, Optional[int]]:
        country = _normalize_country_param(country)
        if not self.repository.get_by_id(policy_id):
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        return self.repository.release_approved_version(policy_id, country)


class ReleasePolicyCountryDraftUseCase:
    """Orquestador UI: Approve → Release."""

    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(
        self,
        policy_id: uuid.UUID,
        country: str,
        data: Optional[ReleasePolicyCountryDraftSchema] = None,
    ) -> PublishPolicyCountryResultSchema:
        country = _normalize_country_param(country)
        payload = data or ReleasePolicyCountryDraftSchema()
        summary = payload.change_summary

        # Actualización de una versión ya publicada → resumen obligatorio.
        prior_published = self.repository.get_country(policy_id, country)
        if prior_published and not summary:
            raise ValidationAppException(AppErrorCode.POLICY_CHANGE_SUMMARY_REQUIRED)
        if not prior_published:
            summary = ''

        approved = ApprovePolicyCountryDraftUseCase(self.repository, self.storage).execute(
            policy_id, country, change_summary=summary,
        )
        published, revoked_version = ReleasePolicyCountryVersionUseCase(self.repository).execute(
            policy_id, country,
        )
        return PublishPolicyCountryResultSchema(
            country=published,
            created_new_version=True,
            revoked_version=revoked_version,
        )


class DiscardPolicyCountryDraftUseCase:
    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID, country: str) -> None:
        country = _normalize_country_param(country)
        if not self.repository.get_by_id(policy_id):
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        deleted = self.repository.delete_draft(policy_id, country)
        if not deleted:
            raise NotFoundException(AppErrorCode.POLICY_DRAFT_NOT_FOUND)
        try:
            self.storage.delete_file(POLICY_BUCKET, deleted.object_key)
        except Exception:
            logger.exception('Failed to delete draft object %s', deleted.object_key)


class GetPolicyCountryContentUseCase:
    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(
        self,
        policy_id: uuid.UUID,
        country: str,
        *,
        status: Optional[str] = None,
    ) -> PolicyCountryContentSchema:
        country = _normalize_country_param(country)
        policy = self.repository.get_by_id(policy_id)
        if not policy:
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)

        want_draft = (status or '').strip().lower() == PolicyCountryStatus.DRAFT.value
        if want_draft:
            row = self.repository.get_draft(policy_id, country)
            if not row:
                raise NotFoundException(AppErrorCode.POLICY_DRAFT_NOT_FOUND)
        else:
            row = self.repository.get_country(policy_id, country)
            if not row:
                raise NotFoundException(AppErrorCode.POLICY_COUNTRY_NOT_FOUND)

        raw = _download_markdown(self.storage, row.object_key)
        return PolicyCountryContentSchema(
            policy_id=policy.id,
            policy_code=policy.code,
            audience=policy.audience,
            country=row.country,
            version=row.version,
            status=row.status,
            title=row.title,
            markdown=raw.decode('utf-8'),
            object_key=row.object_key,
            content_hash=row.content_hash,
            byte_size=row.byte_size,
            change_summary=getattr(row, 'change_summary', '') or '',
            updated_at=row.updated_at,
        )


class ListPolicyCountryVersionsUseCase:
    def __init__(self, repository: IPolicyRepository):
        self.repository = repository

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID, country: str) -> list[PolicyCountrySummarySchema]:
        country = _normalize_country_param(country)
        if not self.repository.get_by_id(policy_id):
            raise NotFoundException(AppErrorCode.POLICY_NOT_FOUND)
        return self.repository.list_country_versions(policy_id, country)


class DeletePolicyCountryUseCase:
    def __init__(self, repository: IPolicyRepository, storage: IStorageService):
        self.repository = repository
        self.storage = storage

    @trace_layer('application')
    def execute(self, policy_id: uuid.UUID, country: str) -> None:
        country = _normalize_country_param(country)
        versions = self.repository.list_country_versions(policy_id, country)
        draft = self.repository.get_draft(policy_id, country)
        if not versions and not draft:
            raise NotFoundException(AppErrorCode.POLICY_COUNTRY_NOT_FOUND)

        keys = [v.object_key for v in versions]
        if draft:
            keys.append(draft.object_key)

        if not self.repository.delete_country(policy_id, country):
            raise NotFoundException(AppErrorCode.POLICY_COUNTRY_NOT_FOUND)

        for object_key in keys:
            try:
                self.storage.delete_file(POLICY_BUCKET, object_key)
            except Exception:
                logger.exception('Failed to delete policy country object %s', object_key)
