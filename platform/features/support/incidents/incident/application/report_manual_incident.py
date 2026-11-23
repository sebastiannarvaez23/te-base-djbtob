"""
ReportManualIncidentUseCase — incidencia voluntaria (assistant u otros).

No requiere draft de un 500: congela el anillo de logs de la sesión, el
``ui_context`` del cliente y la conversación adjunta, y materializa la
incidencia de inmediato.

Cuando ``source`` es ``assistant``, el módulo/funcionalidad de la
incidencia se resuelven a la feature ``assistant.chat`` (no a la
pantalla donde el usuario tenía abierto el chat).
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from core.errors.codes import AppErrorCode
from core.errors.exceptions import ValidationAppException
from platform.features.support.incidents.incident.domain.interfaces import (
    IFeatureRefResolver,
    IIncidentNotifier,
    IIncidentRepository,
    ISessionLogBuffer,
)
from platform.features.support.incidents.incident.application.frontend_context import (
    build_frontend_context_snapshot,
)
from platform.features.support.incidents.incident.domain.schemas import IncidentCreate, IncidentView
from core.trace import trace_layer

logger = logging.getLogger('app.api')

# Soft ceiling so a long chat cannot blow up the JSONField.
_MAX_CONVERSATION_BYTES = 200_000

ASSISTANT_CHAT_FEATURE_KEY = 'assistant.chat'
SOURCE_ASSISTANT = 'assistant'
SOURCE_TOOLBAR = 'toolbar'
KIND_INCIDENT = 'incident'
KIND_SUGGESTION = 'suggestion'


class ReportManualIncidentUseCase:

    def __init__(
        self,
        repository: IIncidentRepository,
        buffer: ISessionLogBuffer,
        notifier: IIncidentNotifier,
        *,
        feature_resolver: Optional[IFeatureRefResolver] = None,
    ):
        self._repo = repository
        self._buffer = buffer
        self._notifier = notifier
        self._feature_resolver = feature_resolver

    @trace_layer('application')
    def execute(
        self,
        *,
        session_id: str,
        comment: str,
        conversation: dict,
        ui_context: Optional[dict] = None,
        reporter: Optional[dict[str, Any]] = None,
        source: str = SOURCE_ASSISTANT,
        kind: str = KIND_INCIDENT,
        frontend_logs: Optional[list[Any]] = None,
        frontend_context: Optional[dict[str, Any]] = None,
    ) -> IncidentView:
        comment = (comment or '').strip()
        if not comment:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        if kind not in (KIND_INCIDENT, KIND_SUGGESTION):
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)

        conversation = conversation if isinstance(conversation, dict) else {}
        raw_size = len(json.dumps(conversation, ensure_ascii=False).encode('utf-8'))
        if raw_size > _MAX_CONVERSATION_BYTES:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)

        source = (source or SOURCE_ASSISTANT).strip().lower()
        if source not in (SOURCE_ASSISTANT, SOURCE_TOOLBAR):
            source = SOURCE_ASSISTANT
        # Suggestions only exist in the toolbar "help us improve" panel.
        if kind == KIND_SUGGESTION and source != SOURCE_TOOLBAR:
            raise ValidationAppException(AppErrorCode.VALIDATION_ERROR)
        is_suggestion = kind == KIND_SUGGESTION

        reporter = reporter or {}
        client_ui = ui_context if isinstance(ui_context, dict) else {}
        if not client_ui:
            nested = conversation.get('ui_context')
            client_ui = nested if isinstance(nested, dict) else {}

        route = str(client_ui.get('route') or '')
        module_id, functionality_id, page_section = self._resolve_refs(
            source=source,
            client_ui=client_ui,
        )

        last_transactions = self._buffer.snapshot(session_id) if session_id else []
        now = datetime.now(timezone.utc).isoformat()
        token = secrets.token_urlsafe(32)

        if source == SOURCE_ASSISTANT:
            error = {
                'code': 'ASSISTANT_REPORT',
                'exception_type': 'ManualReport',
                'message': 'Voluntary report from assistant',
                'path': route or '/assistant',
                'method': 'ASSISTANT',
                'http_status': None,
                'feature_key': ASSISTANT_CHAT_FEATURE_KEY,
            }
            origin = SOURCE_ASSISTANT
            method = 'ASSISTANT'
            path = route or '/assistant'
        else:
            error = {
                'code': 'TOOLBAR_SUGGESTION' if is_suggestion else 'TOOLBAR_REPORT',
                'exception_type': 'Suggestion' if is_suggestion else 'ManualReport',
                'message': (
                    'Improvement suggestion from toolbar'
                    if is_suggestion
                    else 'Voluntary report from toolbar'
                ),
                'path': route or '/',
                'method': 'TOOLBAR',
                'http_status': None,
            }
            origin = SOURCE_TOOLBAR
            method = 'TOOLBAR'
            path = route or '/'

        data = IncidentCreate(
            token=token,
            kind=kind,
            trace_id='',
            severity='low' if is_suggestion else 'medium',
            schema_name=reporter.get('schema_name', '') or '',
            company_id=reporter.get('company_id', '') or '',
            module_id=module_id,
            functionality_id=functionality_id,
            page_section=page_section,
            reporter_user_id=reporter.get('user_id', '') or '',
            reporter_username=reporter.get('username', '') or '',
            reporter_email=reporter.get('email', '') or '',
            error=error,
            snapshot={
                'source': source,
                'kind': kind,
                'failed_request': {
                    'request_id': '',
                    'ts': now,
                    'origin': origin,
                    'method': method,
                    'path': path,
                    'query': None,
                    'request_body': '-',
                    'status': None,
                    'response_body': '-',
                    'duration_ms': None,
                    'logs': [],
                    'module_id': module_id,
                    'functionality_id': functionality_id,
                    'page_section': page_section,
                    'feature_key': (
                        ASSISTANT_CHAT_FEATURE_KEY
                        if source == SOURCE_ASSISTANT
                        else str(client_ui.get('feature_key') or '')
                    ),
                },
                'last_transactions': last_transactions,
                'conversation': conversation,
                'ui_context': {
                    str(k): str(v)
                    for k, v in client_ui.items()
                    if v is not None and str(v).strip()
                },
                'frontend_context': build_frontend_context_snapshot(
                    frontend_context,
                    legacy_frontend_logs=frontend_logs,
                ),
            },
            user_comment=comment,
        )

        incident = self._repo.create(data)
        try:
            self._notifier.notify_created(incident)
        except Exception as exc:
            logger.warning(
                'INCIDENT_NOTIFY_DISPATCH_FAILED code=%s error=%s',
                incident.code, exc,
            )
        return incident

    def _resolve_refs(
        self,
        *,
        source: str,
        client_ui: dict[str, Any],
    ) -> tuple[str, str, str]:
        """Devuelve (module_id, functionality_id, page_section) desde el body del cliente."""
        if source == SOURCE_ASSISTANT:
            module_id, functionality_id = self._resolve_feature_refs(
                ASSISTANT_CHAT_FEATURE_KEY,
            )
            page_section = str(client_ui.get('page_section') or 'chat')
            return module_id, functionality_id, page_section[:63]

        module_id = str(client_ui.get('module_id') or '')
        functionality_id = str(client_ui.get('functionality_id') or '')
        feature_key = str(client_ui.get('feature_key') or '').strip()
        if not functionality_id and feature_key:
            mod, fn = self._resolve_feature_refs(feature_key)
            if fn:
                module_id = module_id or mod
                functionality_id = fn
        page_section = str(client_ui.get('page_section') or '')
        return module_id, functionality_id, page_section[:63]

    def _resolve_feature_refs(self, feature_key: str) -> tuple[str, str]:
        if self._feature_resolver is None:
            return '', ''
        return self._feature_resolver.resolve(feature_key)
