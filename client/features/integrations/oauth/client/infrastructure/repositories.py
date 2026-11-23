"""Django ORM adapters for Integration Application OAuth.

Status-guarded writes (``allowed_from``) run inside ``transaction.atomic``
with either a conditional ``UPDATE … WHERE status IN (…)`` or a
``SELECT … FOR UPDATE`` row lock, so concurrent lifecycle calls serialize.
"""
from __future__ import annotations

import uuid
from typing import Optional, Sequence

from django.db import transaction
from django.db.models import Max, Prefetch, Q
from django.utils import timezone

from client.features.integrations.oauth.client.domain.interfaces import IIntegrationApplicationRepository
from client.features.integrations.oauth.client.domain.schemas import (
    CreateIntegrationApplicationSchema,
    IntegrationApplicationSchema,
    UpdateIntegrationApplicationSchema,
)
from client.features.integrations.oauth.client.models import (
    IntegrationApplication,
    IntegrationApplicationScope,
    IntegrationApplicationSecret,
)
from core.query.core import PaginatedQuery, PaginatedResult

_ACTIVE_SECRETS = 'active_secrets'


def _with_relations(qs):
    return qs.prefetch_related(
        'granted_scopes',
        Prefetch(
            'secrets',
            queryset=IntegrationApplicationSecret.objects.filter(is_active=True).only(
                'id', 'application_id', 'secret_prefix', 'version',
            ),
            to_attr=_ACTIVE_SECRETS,
        ),
    )


class DjangoIntegrationApplicationRepository(IIntegrationApplicationRepository):

    def list_all(self, query: PaginatedQuery) -> PaginatedResult:
        qs = IntegrationApplication.objects.all()
        f = query.filters
        if 'name' in f:
            qs = qs.filter(name__icontains=f['name'])
        if 'status' in f:
            qs = qs.filter(status=f['status'])
        if 'environment' in f:
            qs = qs.filter(environment=f['environment'])
        if 'q' in f:
            qs = qs.filter(
                Q(name__icontains=f['q'])
                | Q(client_id__icontains=f['q'])
                | Q(description__icontains=f['q'])
            )
        qs = _with_relations(qs.order_by('name', 'id'))

        if query.unpaginated:
            items = [self._to_schema(app) for app in qs]
            return PaginatedResult(
                items=items, total=len(items), page=0, page_size=0, total_pages=1,
            )

        total = qs.count()
        items = [self._to_schema(app) for app in qs[query.offset: query.offset + query.limit]]
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        return PaginatedResult(
            items=items, total=total, page=query.page,
            page_size=query.page_size, total_pages=total_pages,
        )

    def get_by_id(self, app_id: uuid.UUID) -> Optional[IntegrationApplicationSchema]:
        return self._load(pk=app_id)

    def get_by_client_id(self, client_id: str) -> Optional[IntegrationApplicationSchema]:
        return self._load(client_id=client_id)

    @transaction.atomic
    def create(
        self,
        data: CreateIntegrationApplicationSchema,
        *,
        client_id: str,
        secret_hash: str,
        secret_prefix: str,
        created_by: uuid.UUID | None,
    ) -> IntegrationApplicationSchema:
        app = IntegrationApplication.objects.create(
            name=data.name,
            description=data.description,
            client_id=client_id,
            environment=data.environment,
            created_by=created_by,
        )
        IntegrationApplicationSecret.objects.create(
            application=app,
            secret_hash=secret_hash,
            secret_prefix=secret_prefix,
            version=1,
            is_active=True,
        )
        self._write_scopes(app, data.scopes)
        return self._load(pk=app.pk)

    @transaction.atomic
    def update(
        self,
        app_id: uuid.UUID,
        data: UpdateIntegrationApplicationSchema,
        *,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        app = self._lock(app_id, allowed_from)
        if app is None:
            return None

        fields = data.model_dump(exclude_none=True, exclude={'scopes'})
        for name, value in fields.items():
            setattr(app, name, value)
        if fields:
            app.save(update_fields=[*fields, 'updated_at'])

        if data.scopes is not None:
            self._write_scopes(app, data.scopes)
            if not fields:
                app.save(update_fields=['updated_at'])
        return self._load(pk=app.pk)

    @transaction.atomic
    def change_status(
        self,
        app_id: uuid.UUID,
        *,
        target: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        if not self._compare_and_set_status(app_id, target, allowed_from):
            return None
        return self._load(pk=app_id)

    @transaction.atomic
    def revoke(
        self,
        app_id: uuid.UUID,
        *,
        target: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        if not self._compare_and_set_status(app_id, target, allowed_from):
            return None
        IntegrationApplicationSecret.objects.filter(
            application_id=app_id, is_active=True,
        ).update(is_active=False, revoked_at=timezone.now())
        return self._load(pk=app_id)

    @transaction.atomic
    def rotate_secret(
        self,
        app_id: uuid.UUID,
        *,
        secret_hash: str,
        secret_prefix: str,
        allowed_from: frozenset[str],
    ) -> Optional[IntegrationApplicationSchema]:
        app = self._lock(app_id, allowed_from)
        if app is None:
            return None

        secrets_qs = IntegrationApplicationSecret.objects.filter(application=app)
        latest = secrets_qs.aggregate(v=Max('version'))['v'] or 0
        secrets_qs.filter(is_active=True).update(is_active=False, revoked_at=timezone.now())
        IntegrationApplicationSecret.objects.create(
            application=app,
            secret_hash=secret_hash,
            secret_prefix=secret_prefix,
            version=latest + 1,
            is_active=True,
        )
        app.save(update_fields=['updated_at'])
        return self._load(pk=app.pk)

    @transaction.atomic
    def delete(self, app_id: uuid.UUID, *, allowed_from: frozenset[str]) -> bool:
        app = self._lock(app_id, allowed_from)
        if app is None:
            return False
        IntegrationApplicationScope.objects.filter(application=app).delete()
        IntegrationApplicationSecret.objects.filter(application=app).delete()
        app.delete()
        return True

    def get_active_secret_hash(self, app_id: uuid.UUID) -> Optional[str]:
        return (
            IntegrationApplicationSecret.objects
            .filter(application_id=app_id, is_active=True)
            .order_by('-version')
            .values_list('secret_hash', flat=True)
            .first()
        )

    def touch_last_used(self, app_id: uuid.UUID) -> None:
        IntegrationApplication.objects.filter(pk=app_id).update(last_used_at=timezone.now())

    @staticmethod
    def _lock(app_id: uuid.UUID, allowed_from: frozenset[str]) -> Optional[IntegrationApplication]:
        return (
            IntegrationApplication.objects
            .select_for_update()
            .filter(pk=app_id, status__in=allowed_from)
            .first()
        )

    @staticmethod
    def _compare_and_set_status(app_id: uuid.UUID, target: str, allowed_from: frozenset[str]) -> bool:
        updated = IntegrationApplication.objects.filter(
            pk=app_id, status__in=allowed_from,
        ).update(status=target, updated_at=timezone.now())
        return updated == 1

    def _load(self, **lookup) -> Optional[IntegrationApplicationSchema]:
        app = _with_relations(IntegrationApplication.objects.filter(**lookup)).first()
        return self._to_schema(app) if app else None

    @staticmethod
    def _write_scopes(app: IntegrationApplication, scopes: Sequence[str]) -> None:
        wanted = set(scopes)
        current = set(
            IntegrationApplicationScope.objects.filter(application=app).values_list('scope', flat=True),
        )
        removed = current - wanted
        if removed:
            IntegrationApplicationScope.objects.filter(application=app, scope__in=removed).delete()
        added = wanted - current
        if added:
            IntegrationApplicationScope.objects.bulk_create([
                IntegrationApplicationScope(application=app, scope=scope) for scope in sorted(added)
            ])

    @staticmethod
    def _to_schema(app: IntegrationApplication) -> IntegrationApplicationSchema:
        active = getattr(app, _ACTIVE_SECRETS, [])
        latest = max(active, key=lambda s: s.version, default=None)
        return IntegrationApplicationSchema(
            id=app.id,
            name=app.name,
            description=app.description or '',
            client_id=app.client_id,
            status=app.status,
            environment=app.environment,
            scopes=sorted(s.scope for s in app.granted_scopes.all()),
            secret_prefix=latest.secret_prefix if latest else None,
            created_by=app.created_by,
            last_used_at=app.last_used_at,
            created_at=app.created_at,
            updated_at=app.updated_at,
        )
