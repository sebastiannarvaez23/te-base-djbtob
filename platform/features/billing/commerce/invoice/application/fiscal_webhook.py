"""Apply inbound Neurana fiscal webhooks via durable inbox.

One transaction per event: the inbox row (unique ``external_event_id``) is
created or locked first, so concurrent deliveries of the same event serialize
and only the first one applies; the invoice row is locked before the status
rank check so out-of-order events cannot downgrade it.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from platform.features.billing.commerce.invoice.models import Invoice, NeuranaWebhookInbox

logger = logging.getLogger('billing.invoice.webhooks')

_ALLOWED = {
    Invoice.FiscalStatus.PENDING,
    Invoice.FiscalStatus.ISSUED,
    Invoice.FiscalStatus.VOIDING,
    Invoice.FiscalStatus.REJECTED,
    Invoice.FiscalStatus.VOIDED,
}
_RANK = {
    '': 0,
    Invoice.FiscalStatus.PENDING: 1,
    Invoice.FiscalStatus.REJECTED: 2,
    Invoice.FiscalStatus.ISSUED: 3,
    Invoice.FiscalStatus.VOIDING: 3,
    Invoice.FiscalStatus.VOIDED: 4,
}


def can_transition(current: str, incoming: str) -> bool:
    if incoming not in _ALLOWED:
        return False
    if current == incoming:
        return True
    return _RANK.get(incoming, 0) >= _RANK.get(current or '', 0)


def _invoice_filter(data: dict) -> Optional[dict]:
    metadata = data.get('metadata') if isinstance(data.get('metadata'), dict) else {}
    wa_invoice_id = metadata.get('wa_invoice_id')
    if wa_invoice_id:
        try:
            return {'pk': UUID(str(wa_invoice_id))}
        except (TypeError, ValueError):
            return None
    external_id = str(data.get('id') or '')
    return {'external_id': external_id} if external_id else None


class ApplyFiscalWebhookUseCase:
    def execute(
        self,
        *,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
        signature: str = '',
        signature_verified: bool = True,
    ) -> dict:
        if not event_id:
            return {'status': 'missing_event_id', 'http_status': 400}

        data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
        lookup = _invoice_filter(data)
        if lookup is None:
            return {'status': 'no_invoice_ref', 'http_status': 400}

        with transaction.atomic():
            inbox, created = NeuranaWebhookInbox.objects.select_for_update().get_or_create(
                external_event_id=event_id,
                defaults={
                    'event_type': event_type or '',
                    'payload': payload,
                    'signature': signature or '',
                    'signature_verified': signature_verified,
                },
            )
            if not created and inbox.processed_at is not None:
                return {'status': 'duplicate', 'http_status': 200, 'message': 'ECO_006'}

            invoice = Invoice.objects.select_for_update().filter(**lookup).first()
            outcome, error = self._apply(invoice, data)
            NeuranaWebhookInbox.objects.filter(pk=inbox.pk).update(
                event_type=event_type or '',
                payload=payload,
                signature=signature or '',
                signature_verified=signature_verified,
                invoice=invoice,
                processing_error=error,
                processed_at=timezone.now(),
            )
        return outcome

    @staticmethod
    def _apply(invoice: Optional[Invoice], data: dict) -> tuple[dict, str]:
        if invoice is None:
            return {'status': 'ignored', 'http_status': 202}, 'invoice_not_found'

        status = str(data.get('status') or '')
        if status and not can_transition(invoice.fiscal_status or '', status):
            return {'status': 'ignored_downgrade', 'http_status': 200}, 'ignored_downgrade'

        updates: dict[str, Any] = {'fiscal_payload': data, 'updated_at': timezone.now()}
        external_id = str(data.get('id') or '')
        number = str(data.get('number') or '')
        if external_id:
            updates['external_id'] = external_id
        if number:
            updates['fiscal_number'] = number
        if status:
            updates['fiscal_status'] = status
        Invoice.objects.filter(pk=invoice.pk).update(**updates)
        return {'status': 'accepted', 'http_status': 202}, ''
