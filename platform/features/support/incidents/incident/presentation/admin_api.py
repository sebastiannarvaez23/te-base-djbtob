"""
Endpoints administrativos de incidencias (portal admin, schema público).

Restringidos a administradores de plataforma vía ``AdminTokenAuthentication``.
"""

import logging
from typing import Optional

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.audit import audit_log
from core.decorators.response import wrap_response
from core.query import PaginatedQuery, validated_query
from core.validators import validated_body
from platform.core.authentication import AdminTokenAuthentication
from platform.features.support.incidents.incident.application.admin_use_cases import (
    GetIncidentUseCase,
    ListIncidentsUseCase,
)
from platform.features.support.incidents.incident.application.attachments import (
    to_attachment_view,
)
from platform.features.support.incidents.incident.application.factory import (
    build_sign_attachments_use_case,
    build_update_status_use_case,
)
from platform.features.support.incidents.incident.domain.schemas import (
    IncidentAttachmentView,
    IncidentView,
)
from platform.features.support.incidents.incident.infrastructure.repositories import (
    DjangoIncidentRepository,
)
from platform.features.support.incidents.incident.presentation.bodies import (
    UpdateIncidentStatusBody,
)
from platform.features.support.incidents.incident.presentation.queries import IncidentListQuery

logger = logging.getLogger('app.api')

_MAX_LIMIT = 100


def _repo():
    return DjangoIncidentRepository()


def _dump(incident: IncidentView, signed: Optional[list[IncidentAttachmentView]] = None) -> dict:
    """Serializa sin exponer rutas internas de object storage."""
    data = incident.model_dump(exclude={'attachments'})
    attachments = signed if signed is not None else [
        to_attachment_view(a) for a in incident.attachments
    ]
    data['attachments'] = [a.model_dump() for a in attachments]
    return data


def _admin_label(user) -> str:
    full = f'{getattr(user, "first_name", "")} {getattr(user, "last_name", "")}'.strip()
    return full or getattr(user, 'username', 'Soporte') or 'Soporte'


class IncidentListView(APIView):
    """Lista incidencias con filtros (status, empresa, fechas) y paginación."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_query(IncidentListQuery)
    def get(self, request, *args, query: PaginatedQuery, **kwargs):
        f = query.filters

        filters = {}
        for key in ('code', 'status', 'severity', 'kind', 'module', 'functionality', 'reporter'):
            if key in f:
                filters[key] = f[key]
        if 'company' in f:
            filters['schema_name'] = f['company']
        if 'from' in f:
            filters['from_date'] = f['from']
        if 'to' in f:
            filters['to_date'] = f['to']

        limit = max(1, min(int(f.get('limit', 50)), _MAX_LIMIT))
        offset = max(0, int(f.get('offset', 0)))

        repo = _repo()
        items = ListIncidentsUseCase(repo).execute(filters, limit=limit, offset=offset)
        total = repo.count(filters)
        return wrap_response({
            'items': [_dump(i) for i in items],
            'total': total,
            'page': (offset // limit) + 1,
            'page_size': limit,
            'total_pages': (total + limit - 1) // limit,
        })


class IncidentDetailView(APIView):
    """Detalle de una incidencia con el snapshot completo."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, incident_id, *args, **kwargs):
        incident = GetIncidentUseCase(_repo()).execute(str(incident_id))
        signed = build_sign_attachments_use_case().execute(incident) if incident.attachments else []
        return wrap_response(_dump(incident, signed))


class IncidentStatusView(APIView):
    """Cambia el estado / asigna / anota la resolución de una incidencia."""

    authentication_classes = [AdminTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(UpdateIncidentStatusBody)
    def patch(self, request, incident_id, *args, body: dict, **kwargs):
        data = body
        assigned = data.get('assigned_admin_id') or None

        incident = build_update_status_use_case().execute(
            str(incident_id),
            status=data['status'],
            assigned_admin_id=assigned,
            resolution_notes=data.get('resolution_notes') or None,
            admin_id=str(request.user.pk),
            admin_label=_admin_label(request.user),
        )
        audit_log(request, 'Incident', str(incident_id), 'UPDATE_STATUS',
                  f'status={data["status"]}')
        return wrap_response(_dump(incident))
