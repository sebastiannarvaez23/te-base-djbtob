"""
Helper de inbox para webhooks entrantes.

Capa fina sobre :class:`DjangoWebhookInboxRepository` que encapsula la
política "guardar primero, procesar después" exigida por el patrón
inbox. El endpoint público de webhooks (FASE 2) la usará así::

    raw_event = receive_webhook(provider, payload_bytes, signature)
    return Response(status=200)   # respondemos ya, procesamos aparte

El worker / use case que consume la inbox (también FASE 2/3) llama a
:meth:`mark_processed` con el resultado.
"""

import json
from typing import Optional

from ...domain.interfaces import IWebhookInboxRepository
from ...domain.schemas import CreateWebhookInboxEntrySchema, WebhookInboxEntrySchema


def store_raw_event(
    repo: IWebhookInboxRepository,
    provider: str,
    payload_bytes: bytes,
    signature_header: str = '',
    signature_verified: bool = False,
    external_event_id: str = '',
    event_type: str = '',
) -> Optional[WebhookInboxEntrySchema]:
    """
    Persiste un evento crudo en la inbox.

    Si ``external_event_id`` no se pasa, se intenta extraer del payload
    como ``id`` (convención común: Stripe usa ``id``, Wompi usa
    ``data.transaction.id``). Si tampoco está, se delega al adapter en
    FASE 2 — aquí solo lo guardamos vacío.

    Devuelve ``None`` si el evento ya existía (provider + external id
    únicos), lo cual indica un reenvío del provider y se debe ignorar.
    """

    if not external_event_id:
        try:
            data = json.loads(payload_bytes.decode('utf-8'))
            external_event_id = str(data.get('id', '')) or str(data.get('event_id', ''))
            if not event_type:
                event_type = str(data.get('type', '') or data.get('event_type', ''))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    if not external_event_id:
        # Sin id externo no podemos garantizar idempotencia. Igual lo
        # almacenamos pero con un placeholder; el worker lo marcará
        # como error de procesamiento.
        external_event_id = f"unidentified:{len(payload_bytes)}"

    existing = repo.get_by_external_id(provider, external_event_id)
    if existing is not None:
        return None

    try:
        payload_dict = json.loads(payload_bytes.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload_dict = {'__raw__': payload_bytes.decode('utf-8', errors='replace')}

    return repo.create(CreateWebhookInboxEntrySchema(
        provider=provider,
        external_event_id=external_event_id,
        event_type=event_type,
        payload=payload_dict,
        signature=signature_header,
        signature_verified=signature_verified,
    ))
