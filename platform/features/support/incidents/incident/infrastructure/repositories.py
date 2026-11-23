"""
DjangoIncidentRepository — persistencia de incidencias (schema público).
"""

from __future__ import annotations

from typing import Optional

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from platform.features.support.incidents.incident.domain.interfaces import (
    AttachmentLimitExceeded,
    IIncidentAttachmentRepository,
    IIncidentRepository,
)
from platform.features.support.incidents.incident.domain.schemas import (
    IncidentAttachment,
    IncidentCreate,
    IncidentFunctionalityRef,
    IncidentModuleRef,
    IncidentView,
)

_MAX_CODE_RETRIES = 5


def _iso(dt):
    return dt.isoformat() if dt else None


def _base_qs():
    from platform.features.support.incidents.incident.models import Incident
    return Incident.objects.select_related('module', 'functionality')


class DjangoIncidentRepository(IIncidentRepository, IIncidentAttachmentRepository):

    def create(self, data: IncidentCreate) -> IncidentView:
        from platform.features.support.incidents.incident.models import Incident

        last_exc = None
        for _ in range(_MAX_CODE_RETRIES):
            code = self._next_code()
            try:
                with transaction.atomic():
                    obj = Incident.objects.create(
                        code=code,
                        token=data.token,
                        kind=data.kind,
                        severity=data.severity,
                        schema_name=data.schema_name,
                        company_id=data.company_id,
                        reporter_user_id=data.reporter_user_id,
                        reporter_username=data.reporter_username,
                        reporter_email=data.reporter_email,
                        trace_id=data.trace_id,
                        module_id=data.module_id or None,
                        functionality_id=data.functionality_id or None,
                        page_section=data.page_section,
                        error=data.error,
                        snapshot=data.snapshot,
                        user_comment=data.user_comment,
                        reported_at=timezone.now(),
                    )
                obj = _base_qs().get(pk=obj.pk)
                return self._to_view(obj)
            except IntegrityError as exc:
                last_exc = exc
                if Incident.objects.filter(token=data.token).exists():
                    raise
                continue
        raise last_exc

    def get_by_token(self, token: str) -> Optional[IncidentView]:
        obj = _base_qs().filter(token=token).first()
        return self._to_view(obj) if obj else None

    def get(self, incident_id: str) -> Optional[IncidentView]:
        obj = _base_qs().filter(id=incident_id).first()
        return self._to_view(obj) if obj else None

    def list(self, filters: dict, limit: int = 50, offset: int = 0) -> list[IncidentView]:
        qs = self._filtered_qs(filters)
        return [self._to_view(o) for o in qs[offset:offset + limit]]

    def count(self, filters: dict) -> int:
        return self._filtered_qs(filters).count()

    @staticmethod
    def _filtered_qs(filters: dict):
        qs = _base_qs()
        if filters.get('code'):
            qs = qs.filter(code__icontains=filters['code'])
        if filters.get('status'):
            qs = qs.filter(status=filters['status'])
        if filters.get('severity'):
            qs = qs.filter(severity=filters['severity'])
        if filters.get('kind'):
            qs = qs.filter(kind=filters['kind'])
        if filters.get('schema_name'):
            qs = qs.filter(schema_name__icontains=filters['schema_name'])
        if filters.get('module'):
            term = filters['module']
            qs = qs.filter(
                Q(module__name__icontains=term) | Q(module__code__icontains=term),
            )
        if filters.get('functionality'):
            term = filters['functionality']
            qs = qs.filter(
                Q(functionality__label__icontains=term) | Q(functionality__key__icontains=term),
            )
        if filters.get('reporter'):
            qs = qs.filter(reporter_username__icontains=filters['reporter'])
        if filters.get('from_date'):
            qs = qs.filter(created_at__gte=filters['from_date'])
        if filters.get('to_date'):
            qs = qs.filter(created_at__lte=filters['to_date'])
        return qs

    def update_status(self, incident_id: str, *, status: str,
                      assigned_admin_id: Optional[str] = None,
                      resolution_notes: Optional[str] = None) -> Optional[IncidentView]:
        from platform.features.support.incidents.incident.models import Incident
        obj = Incident.objects.filter(id=incident_id).first()
        if obj is None:
            return None
        obj.status = status
        if assigned_admin_id is not None:
            obj.assigned_admin_id = assigned_admin_id
        if resolution_notes is not None:
            obj.resolution_notes = resolution_notes
        if status in (Incident.STATUS_RESOLVED, Incident.STATUS_CLOSED) and obj.resolved_at is None:
            obj.resolved_at = timezone.now()
        obj.save()
        obj = _base_qs().get(pk=obj.pk)
        return self._to_view(obj)

    def append_attachments(
        self, incident_id: str, items: list[IncidentAttachment], *, max_total: int,
    ) -> Optional[IncidentView]:
        from platform.features.support.incidents.incident.models import Incident
        with transaction.atomic():
            obj = Incident.objects.select_for_update().filter(id=incident_id).first()
            if obj is None:
                return None
            current = list(obj.attachments or [])
            if len(current) + len(items) > max_total:
                raise AttachmentLimitExceeded()
            obj.attachments = current + [i.model_dump() for i in items]
            obj.save(update_fields=['attachments', 'updated_at'])
        return self.get(incident_id)

    def attachment_objects_for_purge(self, before, statuses) -> list[str]:
        rows = self._purge_qs(before, statuses).exclude(attachments=[]).values_list(
            'attachments', flat=True,
        )
        return [
            str(item['object_name'])
            for attachments in rows
            for item in (attachments or [])
            if isinstance(item, dict) and item.get('object_name')
        ]

    def purge(self, before, statuses) -> int:
        count, _ = self._purge_qs(before, statuses).delete()
        return count

    @staticmethod
    def _purge_qs(before, statuses):
        from platform.features.support.incidents.incident.models import Incident
        return Incident.objects.filter(status__in=list(statuses), updated_at__lt=before)

    def _next_code(self) -> str:
        from platform.features.support.incidents.incident.models import Incident
        year = timezone.now().year
        prefix = f'INC-{year}-'
        seq = Incident.objects.filter(code__startswith=prefix).count() + 1
        return f'{prefix}{seq:04d}'

    @staticmethod
    def _to_view(obj) -> IncidentView:
        module = None
        if getattr(obj, 'module', None):
            module = IncidentModuleRef(
                id=str(obj.module.id),
                code=obj.module.code,
                name=obj.module.name,
            )
        functionality = None
        if getattr(obj, 'functionality', None):
            functionality = IncidentFunctionalityRef(
                id=str(obj.functionality.id),
                key=obj.functionality.key,
                label=obj.functionality.label,
            )
        return IncidentView(
            id=str(obj.id),
            code=obj.code,
            kind=obj.kind,
            status=obj.status,
            severity=obj.severity,
            schema_name=obj.schema_name,
            company_id=obj.company_id,
            reporter_user_id=obj.reporter_user_id,
            reporter_username=obj.reporter_username,
            reporter_email=obj.reporter_email,
            trace_id=obj.trace_id,
            module=module,
            functionality=functionality,
            page_section=obj.page_section or '',
            error=obj.error or {},
            snapshot=obj.snapshot or {},
            user_comment=obj.user_comment,
            attachments=[
                IncidentAttachment.model_validate(a)
                for a in (obj.attachments or [])
                if isinstance(a, dict)
            ],
            assigned_admin_id=obj.assigned_admin_id,
            resolution_notes=obj.resolution_notes,
            created_at=_iso(obj.created_at),
            reported_at=_iso(obj.reported_at),
            resolved_at=_iso(obj.resolved_at),
        )
