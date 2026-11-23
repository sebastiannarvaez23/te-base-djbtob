"""Inbound Neurana ecosystem webhooks (invoice.issued / voided / rejected)."""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from necore.ecosystem.contracts import EventEnvelopeV1
from necore.ecosystem.tracing import parse_traceparent
from necore.ecosystem.webhooks import (
    EVENT_ID_HEADER,
    SIGNATURE_HEADER,
    parse_signature_parts,
    verify_webhook,
)
from necore.errors import AppException
from platform.features.billing.commerce.invoice.application.fiscal_webhook import (
    ApplyFiscalWebhookUseCase,
)
from platform.features.billing.commerce.invoice.infrastructure.fiscal.ne_jwks import (
    get_ne_keyset,
)

logger = logging.getLogger('billing.invoice.webhooks')


def _verify(raw: bytes, header: str) -> str | None:
    """Return the scheme (``v2`` / ``v1``) or ``None`` when the signature is invalid."""
    secrets = list(getattr(settings, 'NE_WEBHOOK_SECRETS', None) or [])
    allow_v1 = bool(getattr(settings, 'NE_WEBHOOK_ALLOW_V1', True))
    keyset = get_ne_keyset()
    try:
        return verify_webhook(raw, header, keyset=keyset, secrets=secrets, allow_v1=allow_v1)[1]
    except AppException:
        pass
    try:
        kid = parse_signature_parts(header).get('kid')
    except AppException:
        return None
    if kid and keyset.get(kid) is None:
        refreshed = get_ne_keyset(force=True)
        if refreshed.get(kid) is not None:
            try:
                return verify_webhook(raw, header, keyset=refreshed, allow_v1=False)[1]
            except AppException:
                return None
    return None


def _error(status: int, code: str, detail: str) -> JsonResponse:
    return JsonResponse({'status': 'error', 'code': code, 'detail': detail}, status=status)


@csrf_exempt
@require_POST
def neurana_webhook(request):
    raw = request.body or b''
    header = request.headers.get(SIGNATURE_HEADER) or ''
    scheme = _verify(raw, header)
    if scheme is None:
        logger.warning('Neurana webhook signature rejected')
        return _error(401, 'ECO_005', 'Invalid signature')

    try:
        envelope = EventEnvelopeV1.model_validate(json.loads(raw.decode('utf-8') or '{}'))
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
        return _error(400, 'ECO_016', 'Payload does not match the v1 contract')

    header_event_id = request.headers.get(EVENT_ID_HEADER) or ''
    if header_event_id and header_event_id != envelope.id:
        return _error(400, 'ECO_016', 'Event id header does not match payload')

    logger.info(
        'neurana_webhook event=%s type=%s scheme=%s ne_trace=%s',
        envelope.id, envelope.type, scheme,
        parse_traceparent(request.headers.get('traceparent')) or '-',
    )
    result = ApplyFiscalWebhookUseCase().execute(
        event_id=envelope.id,
        event_type=envelope.type,
        payload=envelope.to_wire(),
        signature=header[:512],
        signature_verified=True,
    )
    http_status = int(result.get('http_status') or 202)
    body = {'status': result.get('status')}
    if result.get('message'):
        body['message'] = result['message']
        body['detail'] = 'Duplicate event'
    return JsonResponse(body, status=http_status)
