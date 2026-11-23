"""Repositorio Django de políticas, versiones por país y firmas."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from django.db import IntegrityError, transaction
from django.db.models import Exists, Max, OuterRef, Prefetch, Q

from ..domain.enums import PolicyAudience, PolicyCountryStatus, PolicySubjectType
from ..domain.interfaces import IPolicyRepository, IPolicySignatureRepository
from ..domain.schemas import (
    CreatePolicySchema,
    PendingPolicySchema,
    PolicyCountrySummarySchema,
    PolicySchema,
    PolicySignatureSchema,
    SignatoryRef,
    UpdatePolicySchema,
)
from ..models import Policy, PolicyCountry, PolicySignature


def _country_schema(
    obj: PolicyCountry, *, has_draft: bool = False,
) -> PolicyCountrySummarySchema:
    return PolicyCountrySummarySchema(
        id=obj.id,
        country=obj.country,
        version=obj.version,
        status=PolicyCountryStatus(obj.status),
        title=obj.title,
        object_key=obj.object_key,
        content_hash=obj.content_hash,
        byte_size=obj.byte_size,
        change_summary=obj.change_summary or '',
        revoked_at=obj.revoked_at,
        revoked_reason=obj.revoked_reason or '',
        updated_at=obj.updated_at,
        created_at=obj.created_at,
        has_draft=has_draft,
    )


def _published_countries_qs():
    return PolicyCountry.objects.filter(
        status=PolicyCountryStatus.PUBLISHED.value,
    ).order_by('country')


def _draft_countries_qs():
    return PolicyCountry.objects.filter(
        status=PolicyCountryStatus.DRAFT.value,
    ).order_by('country')


def _to_schema(obj: Policy) -> PolicySchema:
    published = list(obj.countries.all())
    # Prefetch may only load published; drafts attached via separate attr if present
    drafts = list(getattr(obj, '_prefetched_drafts', None) or [])
    if not drafts:
        # Fallback when countries prefetch mixed — filter by status
        drafts = [c for c in published if c.status == PolicyCountryStatus.DRAFT.value]
        published = [c for c in published if c.status == PolicyCountryStatus.PUBLISHED.value]

    draft_codes = {d.country for d in drafts}
    return PolicySchema(
        id=obj.id,
        code=obj.code,
        name=obj.name,
        audience=PolicyAudience(obj.audience),
        description=obj.description or '',
        is_active=obj.is_active,
        countries=[
            _country_schema(row, has_draft=row.country in draft_codes)
            for row in published
            if row.status == PolicyCountryStatus.PUBLISHED.value
        ],
        drafts=[_country_schema(row) for row in drafts],
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _signature_schema(obj: PolicySignature) -> PolicySignatureSchema:
    return PolicySignatureSchema(
        id=obj.id,
        policy_id=obj.policy_id,
        policy_code=obj.policy.code if getattr(obj, 'policy', None) else '',
        policy_country_id=obj.policy_country_id,
        country=obj.country,
        content_hash=obj.content_hash,
        subject_type=PolicySubjectType(obj.subject_type),
        subject_id=obj.subject_id,
        tenant_id=obj.tenant_id or None,
        signed_at=obj.signed_at,
        seal=obj.seal,
        seal_algorithm=obj.seal_algorithm,
        canonical_payload=obj.canonical_payload,
        ip_address=obj.ip_address or None,
        user_agent=obj.user_agent or None,
        request_id=obj.request_id or None,
        channel=obj.channel or 'web',
    )


class DjangoPolicyRepository(IPolicyRepository):

    def _qs(self):
        return Policy.objects.prefetch_related(
            Prefetch('countries', queryset=_published_countries_qs(), to_attr='_published'),
            Prefetch(
                'countries',
                queryset=_draft_countries_qs(),
                to_attr='_prefetched_drafts',
            ),
        )

    def _to_schema_from_prefetch(self, obj: Policy) -> PolicySchema:
        published = getattr(obj, '_published', None)
        drafts = getattr(obj, '_prefetched_drafts', None)
        if published is None:
            return _to_schema(obj)
        draft_codes = {d.country for d in (drafts or [])}
        return PolicySchema(
            id=obj.id,
            code=obj.code,
            name=obj.name,
            audience=PolicyAudience(obj.audience),
            description=obj.description or '',
            is_active=obj.is_active,
            countries=[
                _country_schema(row, has_draft=row.country in draft_codes)
                for row in published
            ],
            drafts=[_country_schema(row) for row in (drafts or [])],
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )

    def list(self, filters: dict | None = None) -> List[PolicySchema]:
        qs = self._qs().order_by('code')
        f = filters or {}
        if 'code' in f:
            qs = qs.filter(code__icontains=f['code'])
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'audience' in f:
            qs = qs.filter(audience=f['audience'])
        if 'is_active' in f:
            qs = qs.filter(is_active=f['is_active'])
        if 'country' in f:
            raw = f['country']
            countries = (
                [x.strip().upper() for x in raw.split(',') if x.strip()]
                if isinstance(raw, str)
                else [str(x).strip().upper() for x in (raw or []) if str(x).strip()]
            )
            published = PolicyCountryStatus.PUBLISHED.value
            if len(countries) == 1:
                qs = qs.filter(
                    countries__country=countries[0],
                    countries__status=published,
                ).distinct()
            elif countries:
                qs = qs.filter(
                    countries__country__in=countries,
                    countries__status=published,
                ).distinct()
        if 'q' in f:
            q = f['q']
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q))
        return [self._to_schema_from_prefetch(obj) for obj in qs]

    def get_by_id(self, policy_id: uuid.UUID) -> Optional[PolicySchema]:
        try:
            return self._to_schema_from_prefetch(self._qs().get(id=policy_id))
        except Policy.DoesNotExist:
            return None

    def get_by_code(self, code: str) -> Optional[PolicySchema]:
        try:
            return self._to_schema_from_prefetch(self._qs().get(code=code.strip().upper()))
        except Policy.DoesNotExist:
            return None

    def create(self, data: CreatePolicySchema) -> PolicySchema:
        obj = Policy.objects.create(
            code=data.code,
            name=data.name,
            audience=data.audience.value,
            description=data.description,
            is_active=data.is_active,
        )
        return self._to_schema_from_prefetch(self._qs().get(id=obj.id))

    def update(self, policy_id: uuid.UUID, data: UpdatePolicySchema) -> Optional[PolicySchema]:
        try:
            obj = Policy.objects.get(id=policy_id)
        except Policy.DoesNotExist:
            return None
        fields = data.model_dump(exclude_unset=True)
        for field, value in fields.items():
            setattr(obj, field, value)
        obj.save(update_fields=[*fields.keys(), 'updated_at'] if fields else ['updated_at'])
        return self._to_schema_from_prefetch(self._qs().get(id=obj.id))

    def delete(self, policy_id: uuid.UUID) -> bool:
        with transaction.atomic():
            try:
                obj = Policy.objects.select_for_update().get(id=policy_id)
            except Policy.DoesNotExist:
                return False
            if PolicySignature.objects.filter(policy_id=policy_id).exists():
                from core.errors import AppErrorCode, ConflictException
                raise ConflictException(AppErrorCode.POLICY_HAS_SIGNATURES)
            PolicyCountry.objects.filter(policy_id=policy_id).delete()
            obj.delete()
            return True

    def get_country(
        self, policy_id: uuid.UUID, country: str,
    ) -> Optional[PolicyCountrySummarySchema]:
        try:
            row = PolicyCountry.objects.get(
                policy_id=policy_id,
                country=country.strip().upper(),
                status=PolicyCountryStatus.PUBLISHED.value,
            )
            has_draft = PolicyCountry.objects.filter(
                policy_id=policy_id,
                country=row.country,
                status=PolicyCountryStatus.DRAFT.value,
            ).exists()
            return _country_schema(row, has_draft=has_draft)
        except PolicyCountry.DoesNotExist:
            return None

    def get_draft(
        self, policy_id: uuid.UUID, country: str,
    ) -> Optional[PolicyCountrySummarySchema]:
        try:
            row = PolicyCountry.objects.get(
                policy_id=policy_id,
                country=country.strip().upper(),
                status=PolicyCountryStatus.DRAFT.value,
            )
            return _country_schema(row)
        except PolicyCountry.DoesNotExist:
            return None

    def get_approved(
        self, policy_id: uuid.UUID, country: str,
    ) -> Optional[PolicyCountrySummarySchema]:
        try:
            row = PolicyCountry.objects.get(
                policy_id=policy_id,
                country=country.strip().upper(),
                status=PolicyCountryStatus.APPROVED.value,
            )
            return _country_schema(row)
        except PolicyCountry.DoesNotExist:
            return None

    def list_country_versions(
        self, policy_id: uuid.UUID, country: str,
    ) -> List[PolicyCountrySummarySchema]:
        rows = (
            PolicyCountry.objects
            .filter(policy_id=policy_id, country=country.strip().upper())
            .exclude(status=PolicyCountryStatus.DRAFT.value)
            .order_by('-version')
        )
        return [_country_schema(row) for row in rows]

    def next_country_version(self, policy_id: uuid.UUID, country: str) -> int:
        current = (
            PolicyCountry.objects
            .filter(policy_id=policy_id, country=country.strip().upper())
            .exclude(status=PolicyCountryStatus.DRAFT.value)
            .aggregate(m=Max('version'))
            .get('m')
        )
        return int(current or 0) + 1

    def _resolve_geo_country_id(self, country_code: str) -> Optional[uuid.UUID]:
        from platform.features.geography.location.location.models import Country
        try:
            return Country.objects.only('id').get(code=country_code.strip().upper()).id
        except Country.DoesNotExist:
            return None

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
        country = country.strip().upper()
        row = PolicyCountry.objects.create(
            policy_id=policy_id,
            country=country,
            version=0,
            status=PolicyCountryStatus.DRAFT.value,
            title=title,
            object_key=object_key,
            content_hash=content_hash,
            byte_size=byte_size,
            geo_country_id=geo_country_id,
        )
        Policy.objects.filter(id=policy_id).update(updated_at=datetime.now(timezone.utc))
        return _country_schema(row)

    def update_draft(
        self,
        policy_id: uuid.UUID,
        country: str,
        *,
        title: str,
        content_hash: str,
        byte_size: int,
    ) -> Optional[PolicyCountrySummarySchema]:
        country = country.strip().upper()
        try:
            row = PolicyCountry.objects.get(
                policy_id=policy_id,
                country=country,
                status=PolicyCountryStatus.DRAFT.value,
            )
        except PolicyCountry.DoesNotExist:
            return None
        row.title = title
        row.content_hash = content_hash
        row.byte_size = byte_size
        row.save(update_fields=['title', 'content_hash', 'byte_size', 'updated_at'])
        Policy.objects.filter(id=policy_id).update(updated_at=datetime.now(timezone.utc))
        return _country_schema(row)

    def delete_draft(
        self, policy_id: uuid.UUID, country: str,
    ) -> Optional[PolicyCountrySummarySchema]:
        country = country.strip().upper()
        try:
            row = PolicyCountry.objects.get(
                policy_id=policy_id,
                country=country,
                status=PolicyCountryStatus.DRAFT.value,
            )
        except PolicyCountry.DoesNotExist:
            return None
        summary = _country_schema(row)
        row.delete()
        return summary

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
        country = country.strip().upper()
        row = PolicyCountry.objects.create(
            policy_id=policy_id,
            country=country,
            version=version,
            status=PolicyCountryStatus.APPROVED.value,
            title=title,
            object_key=object_key,
            content_hash=content_hash,
            byte_size=byte_size,
            change_summary=(change_summary or '').strip(),
            geo_country_id=self._resolve_geo_country_id(country),
        )
        Policy.objects.filter(id=policy_id).update(updated_at=datetime.now(timezone.utc))
        return _country_schema(row)

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
    ) -> Tuple[PolicyCountrySummarySchema, Optional[PolicyCountrySummarySchema]]:
        with transaction.atomic():
            approved = self.create_approved_version(
                policy_id,
                country=country,
                version=version,
                title=title,
                object_key=object_key,
                content_hash=content_hash,
                byte_size=byte_size,
                change_summary=change_summary,
            )
            deleted = self.delete_draft(policy_id, country)
            return approved, deleted

    def release_approved_version(
        self,
        policy_id: uuid.UUID,
        country: str,
        *,
        revoke_reason: str = 'superseded',
    ) -> Tuple[PolicyCountrySummarySchema, Optional[int]]:
        country = country.strip().upper()
        now = datetime.now(timezone.utc)
        with transaction.atomic():
            try:
                approved = (
                    PolicyCountry.objects
                    .select_for_update()
                    .get(
                        policy_id=policy_id,
                        country=country,
                        status=PolicyCountryStatus.APPROVED.value,
                    )
                )
            except PolicyCountry.DoesNotExist:
                from core.errors import AppErrorCode, ConflictException
                raise ConflictException(AppErrorCode.POLICY_NOT_APPROVED)

            previous = (
                PolicyCountry.objects
                .filter(
                    policy_id=policy_id,
                    country=country,
                    status=PolicyCountryStatus.PUBLISHED.value,
                )
                .first()
            )
            revoked_version = previous.version if previous else None
            if previous:
                previous.status = PolicyCountryStatus.REVOKED.value
                previous.revoked_at = now
                previous.revoked_reason = revoke_reason or 'superseded'
                previous.save(update_fields=[
                    'status', 'revoked_at', 'revoked_reason', 'updated_at',
                ])

            approved.status = PolicyCountryStatus.PUBLISHED.value
            approved.save(update_fields=['status', 'updated_at'])
            Policy.objects.filter(id=policy_id).update(updated_at=now)
            return _country_schema(approved), revoked_version

    def delete_country(self, policy_id: uuid.UUID, country: str) -> bool:
        country = country.strip().upper()
        versions = list(PolicyCountry.objects.filter(policy_id=policy_id, country=country))
        if not versions:
            return False
        version_ids = [v.id for v in versions]
        if PolicySignature.objects.filter(policy_country_id__in=version_ids).exists():
            from core.errors import AppErrorCode, ConflictException
            raise ConflictException(AppErrorCode.POLICY_HAS_SIGNATURES)
        PolicyCountry.objects.filter(id__in=version_ids).delete()
        return True

    def list_country_object_keys(self, policy_id: uuid.UUID) -> List[str]:
        return list(
            PolicyCountry.objects.filter(policy_id=policy_id).values_list('object_key', flat=True),
        )


class DjangoPolicySignatureRepository(IPolicySignatureRepository):

    def _qs(self):
        return PolicySignature.objects.select_related('policy', 'policy_country')

    def create(self, data: PolicySignatureSchema) -> PolicySignatureSchema:
        try:
            with transaction.atomic():
                obj = PolicySignature.objects.create(
                    id=data.id,
                    policy_id=data.policy_id,
                    policy_country_id=data.policy_country_id,
                    country=data.country,
                    content_hash=data.content_hash,
                    subject_type=data.subject_type.value,
                    subject_id=data.subject_id,
                    tenant_id=data.tenant_id or '',
                    signed_at=data.signed_at,
                    seal=data.seal,
                    seal_algorithm=data.seal_algorithm,
                    canonical_payload=data.canonical_payload,
                    ip_address=data.ip_address or '',
                    user_agent=data.user_agent or '',
                    request_id=data.request_id or '',
                    channel=data.channel or 'web',
                )
        except IntegrityError as exc:
            from core.errors import AppErrorCode, ConflictException
            raise ConflictException(AppErrorCode.POLICY_ALREADY_SIGNED) from exc
        return _signature_schema(self._qs().get(id=obj.id))

    def get_by_id(self, signature_id: uuid.UUID) -> Optional[PolicySignatureSchema]:
        try:
            return _signature_schema(self._qs().get(id=signature_id))
        except PolicySignature.DoesNotExist:
            return None

    def find_for_version(
        self,
        *,
        subject: SignatoryRef,
        policy_country_id: uuid.UUID,
        content_hash: str,
    ) -> Optional[PolicySignatureSchema]:
        try:
            obj = self._qs().get(
                subject_type=subject.subject_type.value,
                subject_id=subject.subject_id,
                policy_country_id=policy_country_id,
                content_hash=content_hash,
            )
            return _signature_schema(obj)
        except PolicySignature.DoesNotExist:
            return None

    def list_for_policy(
        self, policy_id: uuid.UUID, filters: dict | None = None,
    ) -> List[PolicySignatureSchema]:
        qs = self._qs().filter(policy_id=policy_id).order_by('-signed_at')
        f = filters or {}
        if 'country' in f:
            qs = qs.filter(country=str(f['country']).strip().upper())
        if 'subject_id' in f:
            qs = qs.filter(subject_id=f['subject_id'])
        if 'subject_type' in f:
            qs = qs.filter(subject_type=f['subject_type'])
        return [_signature_schema(obj) for obj in qs]

    def list_pending_for_subject(
        self,
        *,
        subject: SignatoryRef,
        country: str,
        policy_codes: Sequence[str] | None = None,
    ) -> List[PendingPolicySchema]:
        from platform.features.compliance.policy.policy.domain.required_codes import (
            normalize_policy_codes,
        )

        country = country.strip().upper()
        audience = subject.subject_type.value
        if policy_codes is not None:
            codes = normalize_policy_codes(policy_codes)
            if not codes:
                return []
        else:
            codes = None

        signed = PolicySignature.objects.filter(
            subject_type=subject.subject_type.value,
            subject_id=subject.subject_id,
            policy_country_id=OuterRef('pk'),
            content_hash=OuterRef('content_hash'),
        )
        rows = (
            PolicyCountry.objects
            .select_related('policy')
            .filter(
                country=country,
                status=PolicyCountryStatus.PUBLISHED.value,
                policy__is_active=True,
                policy__audience=audience,
            )
            .annotate(already_signed=Exists(signed))
            .filter(already_signed=False)
            .order_by('policy__code')
        )
        if codes is not None:
            rows = rows.filter(policy__code__in=codes)
        return [
            PendingPolicySchema(
                policy_id=row.policy_id,
                code=row.policy.code,
                name=row.policy.name,
                audience=PolicyAudience(row.policy.audience),
                country=row.country,
                version=row.version,
                title=row.title,
                content_hash=row.content_hash,
                policy_country_id=row.id,
            )
            for row in rows
        ]
