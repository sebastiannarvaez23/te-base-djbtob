import logging
from typing import Any

from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.auth.cookie_authentication import JWTAccessAuthentication
from core.decorators.response import wrap_response
from core.errors.codes import AppErrorCode
from core.errors.exceptions import ValidationAppException
from core.validators import validated_body
from platform.features.support.incidents.incident.application.attachments import (
    to_attachment_view,
)
from platform.features.support.incidents.incident.application.factory import (
    build_attach_media_use_case,
    build_report_manual_use_case,
    build_report_use_case,
)
from platform.features.support.incidents.incident.domain.attachment_policy import (
    MAX_ATTACHMENTS,
    MAX_NAME_LENGTH,
    MAX_VIDEO_BYTES,
)
from platform.features.support.incidents.incident.domain.schemas import AttachmentUpload
from platform.features.support.incidents.incident import integration as incident_integration
from platform.features.support.incidents.incident.presentation.bodies import (
    ReportIncidentBody,
    ReportManualIncidentBody,
)

logger = logging.getLogger('app.api')


class ReportIncidentAPIView(APIView):
    """El usuario reporta el error 500 que acaba de recibir.

    Recibe el ``token`` que vino en el envelope de error y (opcional) un
    comentario. Materializa la incidencia con la evidencia congelada y responde
    con el código. Idempotente: reportar dos veces devuelve la misma incidencia.
    """

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(ReportIncidentBody)
    def post(self, request, *args, body: dict, **kwargs):

        reporter = {
            'user_id': str(request.user.pk),
            'username': getattr(request.user, 'username', '') or '',
            'email': getattr(request.user, 'email', '') or '',
            'schema_name': getattr(getattr(request, 'tenant', None), 'schema_name', '') or '',
            'company_id': str(getattr(getattr(request.user, 'company', None), 'id', '') or ''),
        }

        frontend_logs = body.get('frontend_logs') or []
        frontend_context = body.get('frontend_context') or {}
        logger.info(
            'INCIDENT_REPORT frontend_logs=%s frontend_context_keys=%s',
            len(frontend_logs),
            len(frontend_context),
        )
        incident = build_report_use_case().execute(
            body['token'],
            comment=body.get('comment', '') or '',
            reporter=reporter,
            frontend_logs=frontend_logs,
            frontend_context=frontend_context or None,
        )
        return wrap_response(
            {'code': incident.code},
            status_code=201,
            message='Incident Reported',
        )


class ReportManualIncidentAPIView(APIView):
    """Reporte voluntario (p.ej. desde assistant) sin draft de un 500.

    Adjunta conversación + ui_context del cliente y congela el anillo de
    transacciones recientes de la sesión.
    """

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]

    @validated_body(ReportManualIncidentBody)
    def post(self, request, *args, body: dict, **kwargs):
        session_id = incident_integration.resolve_client_session_id(request) or ''
        reporter = {
            'user_id': str(request.user.pk),
            'username': getattr(request.user, 'username', '') or '',
            'email': getattr(request.user, 'email', '') or '',
            'schema_name': getattr(getattr(request, 'tenant', None), 'schema_name', '') or '',
            'company_id': str(getattr(getattr(request.user, 'company', None), 'id', '') or ''),
        }
        frontend_logs = body.get('frontend_logs') or []
        frontend_context = body.get('frontend_context') or {}
        logger.info(
            'INCIDENT_MANUAL_REPORT frontend_logs=%s frontend_context_keys=%s',
            len(frontend_logs),
            len(frontend_context),
        )
        incident = build_report_manual_use_case().execute(
            session_id=session_id,
            comment=body.get('comment', '') or '',
            conversation=body.get('conversation') or {},
            ui_context=body.get('ui_context'),
            reporter=reporter,
            source=body.get('source') or 'assistant',
            kind=body.get('kind') or 'incident',
            frontend_logs=frontend_logs,
            frontend_context=frontend_context or None,
        )
        return wrap_response(
            {'id': incident.id, 'code': incident.code, 'kind': incident.kind},
            status_code=201,
            message='Incident Reported',
        )


class IncidentAttachmentsAPIView(APIView):
    """El reporter adjunta evidencia (imágenes / MP4) a su reporte recién creado.

    Multipart con el campo repetido ``files``. Tipo, tamaño y firma binaria se
    validan en el use case; aquí solo se acota el volumen antes de leer bytes.
    """

    authentication_classes = [JWTAccessAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, incident_id, *args, **kwargs):
        uploads = request.FILES.getlist('files')
        if not uploads:
            raise ValidationAppException(
                AppErrorCode.VALIDATION_ERROR, override_detail='Field "files" is required.',
            )
        if len(uploads) > MAX_ATTACHMENTS:
            raise ValidationAppException(AppErrorCode.INCIDENT_ATTACHMENTS_LIMIT)
        if any(f.size > MAX_VIDEO_BYTES or len(f.name or '') > 2 * MAX_NAME_LENGTH for f in uploads):
            raise ValidationAppException(AppErrorCode.INCIDENT_ATTACHMENT_INVALID)

        files = [
            AttachmentUpload(
                name=f.name or '',
                content_type=getattr(f, 'content_type', '') or '',
                data=f.read(),
            )
            for f in uploads
        ]
        incident = build_attach_media_use_case().execute(
            incident_id=str(incident_id),
            reporter_user_id=str(request.user.pk),
            schema_name=getattr(getattr(request, 'tenant', None), 'schema_name', '') or '',
            files=files,
        )
        return wrap_response(
            {'attachments': [to_attachment_view(a).model_dump() for a in incident.attachments]},
            status_code=201,
            message='Attachments Stored',
        )
