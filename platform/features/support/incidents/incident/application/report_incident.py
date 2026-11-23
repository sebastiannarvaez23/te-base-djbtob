"""
ReportIncidentUseCase — convierte un draft congelado en una incidencia persistida.

Flujo:
  1. Idempotencia: si ya existe una incidencia para el token, la devuelve.
  2. Consume el draft (single-use). Si no existe/expiró → 410 (INC_001).
  3. Crea la incidencia (OPEN) con la evidencia inmutable.
  4. Notifica al admin (best-effort, no bloquea).

La carrera concurrente (dos POST simultáneos) la resuelve la unicidad de
``token``: solo uno obtiene el draft (GETDEL atómico); el otro cae en el paso 1
o en el ``IntegrityError`` que se traduce a la incidencia existente.
"""

import logging
from typing import Any, Optional

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ValidationAppException
from platform.features.support.incidents.incident.domain.interfaces import (
    IFeatureRefResolver,
    IIncidentDraftStore,
    IIncidentNotifier,
    IIncidentRepository,
)
from platform.features.support.incidents.incident.application.frontend_context import (
    build_frontend_context_snapshot,
)
from platform.features.support.incidents.incident.domain.schemas import IncidentCreate, IncidentView
from core.trace import trace_layer

logger = logging.getLogger('app.api')


class ReportIncidentUseCase:

    def __init__(
        self,
        repository: IIncidentRepository,
        draft_store: IIncidentDraftStore,
        notifier: IIncidentNotifier,
        *,
        feature_resolver: IFeatureRefResolver | None = None,
    ):
        self._repo = repository
        self._draft_store = draft_store
        self._notifier = notifier
        self._feature_resolver = feature_resolver

    @trace_layer('application')
    def execute(
        self,
        token: str,
        *,
        comment: str = '',
        reporter: Optional[dict[str, Any]] = None,
        frontend_logs: Optional[list[Any]] = None,
        frontend_context: Optional[dict[str, Any]] = None,
    ) -> IncidentView:
        if not token:
            raise ValidationAppException(AppErrorCode.INCIDENT_DRAFT_NOT_FOUND)

        # 1. Idempotencia: token ya reportado.
        existing = self._repo.get_by_token(token)
        if existing is not None:
            return existing

        # 2. Consumir el draft (single-use).
        draft = self._draft_store.pop(token)
        if not draft:
            raise ValidationAppException(AppErrorCode.INCIDENT_DRAFT_NOT_FOUND)

        # 3. Crear la incidencia.
        reporter = reporter or {}
        failed = draft.get('failed_request') or {}
        error = draft.get('error') or {}
        module_id, functionality_id, page_section = self._resolve_refs(failed, error)
        data = IncidentCreate(
            token=token,
            trace_id=failed.get('request_id', ''),
            schema_name=reporter.get('schema_name', '') or draft.get('schema_name', ''),
            company_id=reporter.get('company_id', ''),
            module_id=module_id,
            functionality_id=functionality_id,
            page_section=page_section,
            reporter_user_id=reporter.get('user_id', '') or draft.get('session_id', ''),
            reporter_username=reporter.get('username', ''),
            reporter_email=reporter.get('email', ''),
            error=draft.get('error') or {},
            snapshot={
                'failed_request': draft.get('failed_request') or {},
                'last_transactions': draft.get('last_transactions') or [],
                'frontend_context': build_frontend_context_snapshot(
                    frontend_context,
                    legacy_frontend_logs=frontend_logs,
                    draft_frontend_logs=draft.get('frontend_logs'),
                ),
            },
            user_comment=comment or '',
        )
        try:
            incident = self._repo.create(data)
        except Exception:
            # Carrera: otro request creó la incidencia con este token entre el
            # paso 1 y el create. Devolvemos la existente (idempotencia).
            existing = self._repo.get_by_token(token)
            if existing is not None:
                return existing
            raise

        # 4. Notificar (best-effort).
        try:
            self._notifier.notify_created(incident)
        except Exception as exc:
            logger.warning('INCIDENT_NOTIFY_DISPATCH_FAILED code=%s error=%s', incident.code, exc)

        return incident

    def _resolve_refs(self, failed: dict, error: dict) -> tuple[str, str, str]:
        """Resuelve FKs de catálogo solo al materializar la incidencia."""
        module_id = str(failed.get('module_id') or '')
        functionality_id = str(failed.get('functionality_id') or '')
        page_section = str(failed.get('page_section') or '')[:63]
        feature_key = str(
            failed.get('feature_key')
            or (error.get('ui_context') or {}).get('feature_key')
            or '',
        ).strip()
        if functionality_id or not feature_key or self._feature_resolver is None:
            return module_id, functionality_id, page_section
        mod, fn = self._feature_resolver.resolve(feature_key)
        return (module_id or mod), fn, page_section
