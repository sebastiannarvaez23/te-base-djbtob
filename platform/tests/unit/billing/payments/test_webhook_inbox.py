"""
Tests del helper :func:`store_raw_event` (patrón inbox para webhooks).

Sin BD: el repositorio se mockea con :class:`MagicMock`.
"""

import json
import uuid
from unittest.mock import MagicMock

import pytest

from platform.features.billing.commerce.payments.domain.schemas import (
    CreateWebhookInboxEntrySchema,
    WebhookInboxEntrySchema,
)
from platform.features.billing.commerce.payments.infrastructure.webhooks.inbox import store_raw_event


pytestmark = pytest.mark.unit


def _entry(**overrides) -> WebhookInboxEntrySchema:
    defaults = dict(
        id=uuid.uuid4(),
        provider='simulator',
        external_event_id='evt_1',
        event_type='charge.captured',
        payload={'id': 'evt_1'},
        signature='sig',
        signature_verified=True,
    )
    defaults.update(overrides)
    return WebhookInboxEntrySchema(**defaults)


# ── Camino feliz ──────────────────────────────────────────────────────────────


def test_persists_new_event_and_returns_entry():
    repo = MagicMock()
    repo.get_by_external_id.return_value = None
    repo.create.return_value = _entry()

    payload = json.dumps({'id': 'evt_1', 'type': 'charge.captured'}).encode('utf-8')
    result = store_raw_event(repo, 'simulator', payload, signature_header='sig', signature_verified=True)

    assert result is not None
    repo.get_by_external_id.assert_called_once_with('simulator', 'evt_1')
    repo.create.assert_called_once()

    arg = repo.create.call_args.args[0]
    assert isinstance(arg, CreateWebhookInboxEntrySchema)
    assert arg.provider == 'simulator'
    assert arg.external_event_id == 'evt_1'
    assert arg.event_type == 'charge.captured'
    assert arg.signature == 'sig'
    assert arg.signature_verified is True
    assert arg.payload == {'id': 'evt_1', 'type': 'charge.captured'}


# ── Idempotencia ──────────────────────────────────────────────────────────────


def test_returns_none_when_event_already_exists():
    repo = MagicMock()
    repo.get_by_external_id.return_value = _entry()

    payload = json.dumps({'id': 'evt_1', 'type': 'x'}).encode('utf-8')
    result = store_raw_event(repo, 'simulator', payload)

    assert result is None
    repo.create.assert_not_called()


def test_uses_explicit_external_event_id_over_payload_id():
    """Cuando el caller conoce mejor el id (header del provider), gana."""
    repo = MagicMock()
    repo.get_by_external_id.return_value = None
    repo.create.return_value = _entry(external_event_id='evt_from_header')

    payload = json.dumps({'id': 'evt_from_body'}).encode('utf-8')
    store_raw_event(repo, 'simulator', payload, external_event_id='evt_from_header')

    repo.get_by_external_id.assert_called_once_with('simulator', 'evt_from_header')


# ── Extracción de id desde payload ────────────────────────────────────────────


def test_falls_back_to_event_id_field():
    """Algunos providers usan ``event_id`` en vez de ``id``."""
    repo = MagicMock()
    repo.get_by_external_id.return_value = None
    repo.create.return_value = _entry()

    payload = json.dumps({'event_id': 'evt_alt', 'event_type': 'charge.failed'}).encode('utf-8')
    store_raw_event(repo, 'wompi', payload)

    repo.get_by_external_id.assert_called_once_with('wompi', 'evt_alt')
    arg = repo.create.call_args.args[0]
    assert arg.external_event_id == 'evt_alt'
    assert arg.event_type == 'charge.failed'


# ── Payload malformado ────────────────────────────────────────────────────────


def test_handles_unidentified_event_when_no_id_present():
    repo = MagicMock()
    repo.get_by_external_id.return_value = None
    repo.create.return_value = _entry()

    payload = json.dumps({'foo': 'bar'}).encode('utf-8')
    result = store_raw_event(repo, 'simulator', payload)

    assert result is not None
    arg = repo.create.call_args.args[0]
    # El external_event_id contiene el placeholder ``unidentified:<size>``.
    assert arg.external_event_id.startswith('unidentified:')


def test_handles_non_json_payload_gracefully():
    """Payloads no-JSON se almacenan como ``__raw__``."""
    repo = MagicMock()
    repo.get_by_external_id.return_value = None
    repo.create.return_value = _entry()

    payload = b'<xml>weird</xml>'
    store_raw_event(repo, 'wompi', payload)

    arg = repo.create.call_args.args[0]
    assert '__raw__' in arg.payload
    assert arg.external_event_id.startswith('unidentified:')


# ── Verificación de firma ────────────────────────────────────────────────────


def test_signature_verified_flag_is_propagated():
    repo = MagicMock()
    repo.get_by_external_id.return_value = None
    repo.create.return_value = _entry(signature_verified=False)

    payload = json.dumps({'id': 'evt_unsigned'}).encode('utf-8')
    store_raw_event(repo, 'simulator', payload, signature_header='', signature_verified=False)

    arg = repo.create.call_args.args[0]
    assert arg.signature_verified is False
    assert arg.signature == ''
