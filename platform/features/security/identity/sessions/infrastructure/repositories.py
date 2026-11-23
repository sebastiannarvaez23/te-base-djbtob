from datetime import datetime
from uuid import UUID

from django.contrib.auth import get_user_model

from core.auth import refresh_service
from core.query.core import PaginatedQuery, PaginatedResult
from platform.features.security.identity.sessions.domain.interfaces import ISessionRepository
from platform.features.security.identity.sessions.domain.schemas import SessionSchema


def _record_to_schema(record: dict, user_cache: dict) -> SessionSchema:
    """Convert a Redis refresh-token record to a SessionSchema.

    ``user_cache`` maps ``(user_type, user_id_str)`` to a dict with
    username, full_name, company_id, company_name so we avoid N+1 queries.
    """
    user_key = (record['user_type'], record['user_id'])
    user_info = user_cache.get(user_key, {})
    created = datetime.fromisoformat(record['created_at'])
    expires = datetime.fromisoformat(record['expires_at'])

    return SessionSchema(
        id=record.get('session_key', ''),
        user_id=UUID(record['user_id']),
        username=user_info.get('username', '—'),
        user_full_name=user_info.get('full_name', '—'),
        company_id=user_info.get('company_id'),
        company_name=user_info.get('company_name'),
        ip_address=record.get('ip_address') or '—',
        user_agent=record.get('user_agent') or '—',
        created_at=created,
        last_activity=user_info.get('last_login') or created,
        expires_at=expires,
        is_active=datetime.utcnow() < expires,
    )


def _build_user_cache(records: list[dict]) -> dict:
    """Batch-load user info for all records to avoid N+1 queries."""
    admin_ids = set()
    client_ids = set()
    for r in records:
        uid = r['user_id']
        if r['user_type'] == 'admin':
            admin_ids.add(uid)
        else:
            client_ids.add(uid)

    cache = {}

    if admin_ids:
        from platform.features.security.identity.users.models import AdminUser
        for u in AdminUser.objects.filter(pk__in=admin_ids).only(
            'id', 'username', 'first_name', 'last_name', 'last_login',
        ):
            cache[('admin', str(u.pk))] = {
                'username': u.username,
                'full_name': f'{u.first_name} {u.last_name}'.strip(),
                'company_id': None,
                'company_name': None,
                'last_login': u.last_login,
            }

    if client_ids:
        User = get_user_model()
        for u in User.objects.filter(pk__in=client_ids).select_related('company').only(
            'id', 'username', 'first_name', 'last_name', 'last_login',
            'company__id', 'company__name',
        ):
            company = getattr(u, 'company', None)
            cache[('client', str(u.pk))] = {
                'username': u.username,
                'full_name': f'{u.first_name or ""} {u.last_name or ""}'.strip(),
                'company_id': company.id if company else None,
                'company_name': company.name if company else None,
                'last_login': u.last_login,
            }

    return cache


class DjangoSessionRepository(ISessionRepository):

    def get_paginated(self, query: PaginatedQuery) -> PaginatedResult:
        records = refresh_service.list_all()
        user_cache = _build_user_cache(records)

        sessions = [_record_to_schema(r, user_cache) for r in records]

        # Apply filters
        filters = query.filters or {}
        if 'username' in filters:
            term = filters['username'].lower()
            sessions = [
                s for s in sessions
                if term in s.username.lower() or term in s.user_full_name.lower()
            ]
        if 'company' in filters:
            term = filters['company'].lower()
            sessions = [
                s for s in sessions
                if s.company_name and term in s.company_name.lower()
            ]
        if 'ip_address' in filters:
            term = filters['ip_address']
            sessions = [s for s in sessions if term in s.ip_address]

        status_filter = filters.get('status')
        if status_filter == 'active':
            sessions = [s for s in sessions if s.is_active]
        elif status_filter == 'inactive':
            sessions = [s for s in sessions if not s.is_active]

        sessions.sort(key=lambda s: s.created_at, reverse=True)

        total = len(sessions)
        total_pages = (total + query.page_size - 1) // query.page_size if query.page_size else 1
        start = query.offset
        end = start + query.limit
        items = sessions[start:end]

        return PaginatedResult(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=total_pages,
        )

    def kill_session(self, session_id: str) -> bool:
        return refresh_service.revoke_by_session_key(session_id)

    def kill_by_user(self, user_id: UUID) -> int:
        count = 0
        count += refresh_service.revoke_all_for_user(user_id, 'admin')
        count += refresh_service.revoke_all_for_user(user_id, 'client')
        return count

    def kill_by_company(self, company_id: UUID) -> int:
        User = get_user_model()
        user_ids = list(
            User.objects.filter(company_id=company_id).values_list('pk', flat=True)
        )
        return refresh_service.revoke_all_for_users(user_ids, 'client')

    def kill_all(self) -> int:
        return refresh_service.revoke_all()
