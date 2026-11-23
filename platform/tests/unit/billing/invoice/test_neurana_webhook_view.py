"""Inbound Neurana webhook: Ed25519 v2 signatures, JWKS rotation, v1 fallback, contract."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from django.test import RequestFactory

from necore.ecosystem.keys import KeySet, SigningKey, generate_private_key
from necore.ecosystem.webhooks import sign_payload, sign_payload_v2
from platform.features.billing.commerce.invoice.presentation import neurana_webhooks as view

pytestmark = pytest.mark.unit

MODULE = 'platform.features.billing.commerce.invoice.presentation.neurana_webhooks'


def _body(event_id='invoice.issued:1') -> bytes:
    return json.dumps({
        'id': event_id,
        'type': 'invoice.issued',
        'version': '1',
        'producer': 'neurana',
        'product': 'base',
        'occurred_at': '2026-10-27T12:00:00Z',
        'data': {
            'id': str(uuid4()),
            'number': 'NE-1',
            'status': 'issued',
            'metadata': {'wa_invoice_id': str(uuid4())},
        },
    }).encode()


@pytest.fixture
def applied(monkeypatch):
    calls = []

    class _UseCase:
        def execute(self, **kwargs):
            calls.append(kwargs)
            return {'status': 'accepted', 'http_status': 202}

    monkeypatch.setattr(f'{MODULE}.ApplyFiscalWebhookUseCase', _UseCase)
    return calls


def _keysets(monkeypatch, *, cached: KeySet, fresh: KeySet | None = None):
    def _get(*, force=False):
        return (fresh or cached) if force else cached

    monkeypatch.setattr(f'{MODULE}.get_ne_keyset', _get)


def _post(body: bytes, signature: str):
    request = RequestFactory().post(
        '/ecosystem/webhooks/neurana/', data=body, content_type='application/json',
        HTTP_X_NE_SIGNATURE=signature,
    )
    return view.neurana_webhook(request)


def test_v2_signature_accepted(monkeypatch, settings, applied):
    settings.NE_WEBHOOK_SECRETS = []
    key = SigningKey.from_private(generate_private_key())
    _keysets(monkeypatch, cached=KeySet([key]))
    body = _body()
    resp = _post(body, sign_payload_v2(key, body))
    assert resp.status_code == 202
    assert applied[0]['event_id'] == 'invoice.issued:1'
    assert applied[0]['payload']['data']['status'] == 'issued'


def test_rotated_kid_refreshes_jwks_once(monkeypatch, settings, applied):
    settings.NE_WEBHOOK_SECRETS = []
    old = SigningKey.from_private(generate_private_key())
    new = SigningKey.from_private(generate_private_key())
    _keysets(monkeypatch, cached=KeySet([old]), fresh=KeySet([new, old]))
    body = _body()
    assert _post(body, sign_payload_v2(new, body)).status_code == 202


def test_forged_v2_rejected_even_with_valid_v1(monkeypatch, settings, applied):
    settings.NE_WEBHOOK_SECRETS = ['whsec_test_secret_16']
    trusted = SigningKey.from_private(generate_private_key())
    forger = SigningKey.from_private(generate_private_key())
    _keysets(monkeypatch, cached=KeySet([trusted]))
    body = _body()
    signature = sign_payload_v2(forger, body, legacy_secret='whsec_test_secret_16')
    assert _post(body, signature).status_code == 401
    assert applied == []


def test_v1_fallback_when_jwks_unavailable(monkeypatch, settings, applied):
    settings.NE_WEBHOOK_SECRETS = ['whsec_test_secret_16']
    settings.NE_WEBHOOK_ALLOW_V1 = True
    _keysets(monkeypatch, cached=KeySet())
    body = _body()
    assert _post(body, sign_payload('whsec_test_secret_16', body)).status_code == 202

    settings.NE_WEBHOOK_ALLOW_V1 = False
    assert _post(body, sign_payload('whsec_test_secret_16', body)).status_code == 401


def test_ecosystem_client_wiring_builds(settings, tmp_path):
    from necore.ecosystem.keys import private_key_to_pem
    from platform.features.billing.commerce.invoice.infrastructure.fiscal import ecosystem_client

    pem = tmp_path / 'product.pem'
    pem.write_text(private_key_to_pem(generate_private_key()), encoding='ascii')
    settings.NE_ECOSYSTEM_BASE_URL = 'http://api.neurana.local:8000'
    settings.NE_ALLOW_INSECURE_HTTP = True
    settings.NE_PRODUCT_CLIENT_ID = 'base_test'
    settings.NE_PRODUCT_PRIVATE_KEY = ''
    settings.NE_PRODUCT_PRIVATE_KEY_FILE = str(pem)
    client = ecosystem_client.build_ecosystem_client()
    assert client is not None


def test_contract_violation_is_400(monkeypatch, settings, applied):
    key = SigningKey.from_private(generate_private_key())
    _keysets(monkeypatch, cached=KeySet([key]))
    body = json.dumps({'id': 'x', 'type': 'invoice.exploded', 'data': {}}).encode()
    resp = _post(body, sign_payload_v2(key, body))
    assert resp.status_code == 400
    assert json.loads(resp.content)['code'] == 'ECO_016'
    assert applied == []
