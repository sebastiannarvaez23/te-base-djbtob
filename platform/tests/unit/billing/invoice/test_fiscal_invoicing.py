"""Unit tests for Phase 4 fiscal invoicing (payload, issue, webhook, void)."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from platform.features.billing.commerce.invoice.application.fiscal_payload import (
    build_fiscal_customer,
    build_fiscal_lines,
)
from platform.features.billing.commerce.invoice.application.fiscal_issue import (
    ReconcileFiscalPendingUseCase,
    VoidFiscalInvoiceUseCase,
)
from platform.features.billing.commerce.invoice.application.fiscal_webhook import (
    ApplyFiscalWebhookUseCase,
    can_transition,
)
from platform.features.billing.commerce.invoice.domain.fiscal import (
    FiscalIssueRequest,
    FiscalIssueResult,
    FiscalVoidRequest,
)
from platform.features.billing.commerce.invoice.infrastructure.fiscal.local import (
    LocalFiscalInvoicingProvider,
)
from platform.features.billing.commerce.invoice.infrastructure.fiscal.neurana import (
    NeuranaFiscalInvoicingProvider,
)
from platform.features.billing.commerce.invoice.models import Invoice, NeuranaWebhookInbox
from platform.features.billing.commerce.payments.integration.events import InvoiceIssued
from platform.features.billing.commerce.payments.integration.fiscal_invoicing import (
    FiscalInvoicingListener,
    FiscalVoidOnRefundListener,
)

pytestmark = pytest.mark.unit


def test_local_provider_is_noop():
    provider = LocalFiscalInvoicingProvider()
    assert provider.issue(
        FiscalIssueRequest(
            charge_id=uuid4(),
            invoice_id=uuid4(),
            external_ref='c1',
            issue_date='2026-10-20',
            currency='USD',
            customer={},
            lines=[],
        ),
    ) is None
    assert provider.void(FiscalVoidRequest(external_id='x')) is None


def test_neurana_provider_maps_create_and_void():
    calls = {}

    class Client:
        def create_invoice(self, payload, idempotency_key):
            return {'id': 'ne-1', 'number': 'NE-1', 'status': 'issued'}

        def get_invoice(self, _id):
            return None

        def void_invoice(self, invoice_id, *, reason, idempotency_key, external_ref=''):
            calls['void'] = (invoice_id, reason, idempotency_key)
            return {'id': invoice_id, 'number': 'NE-1', 'status': 'voided'}

    provider = NeuranaFiscalInvoicingProvider(client=Client())
    issued = provider.issue(
        FiscalIssueRequest(
            charge_id=uuid4(),
            invoice_id=uuid4(),
            external_ref='c',
            issue_date='2026-10-20',
            currency='USD',
            customer={'tax_id': '1', 'legal_name': 'A'},
            lines=[{'concept_code': 'WA_SUBSCRIPTION', 'description': 'Plan', 'quantity': '1',
                    'unit_price': '100', 'discount': '0', 'tax_codes': ['IVA19']}],
        ),
    )
    assert issued and issued.fiscal_status == 'issued'
    voided = provider.void(FiscalVoidRequest(external_id='ne-1', reason='refund', idempotency_key='k'))
    assert voided and voided.fiscal_status == 'voided'
    assert calls['void'][0] == 'ne-1'


def test_fiscal_payload_uses_promo_and_company(settings):
    settings.NE_DEFAULT_TAX_CODES = []
    settings.NE_TAX_INCLUSIVE = True
    invoice = SimpleNamespace(
        tenant_nit='',
        tenant_name='',
        total_amount=Decimal('80'),
        invoice_number='INV-9',
        metadata={
            'original_amount': '100',
            'discount_amount': '20',
            'recipient_email': 'a@b.co',
            'subscription_name': 'Pro',
        },
    )
    company = SimpleNamespace(nit='901', name='Acme', address='Calle 1')
    customer = build_fiscal_customer(invoice, company=company)
    assert customer['tax_id'] == '901'
    assert customer['email'] == 'a@b.co'
    lines = build_fiscal_lines(invoice)
    assert lines[0]['concept_code'] == 'WA_SUBSCRIPTION'
    assert lines[0]['unit_price'] == '100'
    assert lines[0]['discount'] == '20'
    assert lines[0]['tax_codes'] == []


def test_fiscal_payload_strips_inclusive_iva(settings):
    settings.NE_DEFAULT_TAX_CODES = ['IVA19']
    settings.NE_TAX_INCLUSIVE = True
    settings.NE_DEFAULT_TAX_RATE = '19'
    invoice = SimpleNamespace(
        tenant_nit='1',
        tenant_name='T',
        total_amount=Decimal('119'),
        invoice_number='INV-10',
        metadata={'original_amount': '119', 'discount_amount': '0', 'subscription_name': 'Pro'},
    )
    lines = build_fiscal_lines(invoice)
    assert lines[0]['concept_code'] == 'WA_SUBSCRIPTION'
    assert lines[0]['tax_codes'] == ['IVA19']
    assert lines[0]['unit_price'] == '100.00'
    assert lines[0]['discount'] == '0.00'


class _FakeOutboxRepo:
    def __init__(self):
        self.rows = []

    def enqueue(self, data):
        self.rows.append(data)
        return data, True


def _patch_invoice_lookup(monkeypatch, invoice):
    class _QS:
        def filter(self, **kwargs):
            return self

        def only(self, *a):
            return self

        def first(self):
            return invoice

        def update(self, **kwargs):
            return 1

    monkeypatch.setattr(Invoice.objects, 'filter', lambda **kw: _QS())
    monkeypatch.setattr(
        'platform.features.billing.commerce.payments.integration.fiscal_invoicing.transaction.atomic',
        lambda: __import__('contextlib').nullcontext(),
    )


def test_listener_writes_issue_command_to_outbox(monkeypatch):
    invoice_id = uuid4()
    charge_id = uuid4()
    _patch_invoice_lookup(monkeypatch, SimpleNamespace(
        pk=invoice_id, fiscal_status='', external_id='', source_charge_id=charge_id,
    ))
    repo = _FakeOutboxRepo()
    FiscalInvoicingListener(
        provider_factory=lambda: object(), repository_factory=lambda: repo,
    ).on_invoice_issued(
        InvoiceIssued(invoice_id=invoice_id, company_id=uuid4(), charge_id=charge_id),
    )
    assert len(repo.rows) == 1
    assert repo.rows[0].kind.value == 'issue'
    assert repo.rows[0].idempotency_key == f'issue:{charge_id}'


def test_listener_skips_local_provider(monkeypatch):
    repo = _FakeOutboxRepo()
    FiscalInvoicingListener(
        provider_factory=LocalFiscalInvoicingProvider, repository_factory=lambda: repo,
    ).on_invoice_issued(InvoiceIssued(invoice_id=uuid4(), company_id=uuid4(), charge_id=uuid4()))
    assert repo.rows == []


def test_void_on_refund_writes_void_command(monkeypatch):
    invoice_id = uuid4()
    charge_id = uuid4()
    _patch_invoice_lookup(monkeypatch, SimpleNamespace(
        pk=invoice_id, fiscal_status='issued', external_id='ne-9',
    ))
    repo = _FakeOutboxRepo()
    FiscalVoidOnRefundListener(
        provider_factory=lambda: object(), repository_factory=lambda: repo,
    ).on_payment_refunded(
        SimpleNamespace(is_partial=False, invoice_id=invoice_id, charge_id=charge_id),
    )
    assert repo.rows[0].kind.value == 'void'
    assert repo.rows[0].idempotency_key == f'void:{charge_id}'


def test_webhook_transition_rank():
    assert can_transition('pending', 'issued')
    assert can_transition('issued', 'voided')
    assert can_transition('issued', 'voiding')
    assert can_transition('voiding', 'voided')
    assert can_transition('voiding', 'issued')
    assert not can_transition('issued', 'pending')
    assert not can_transition('voiding', 'pending')


class _AtomicNull:
    def __call__(self):
        return __import__('contextlib').nullcontext()


def _patch_webhook_models(monkeypatch, *, invoice, inbox_processed=False, created=True):
    stored = []

    class _InvQS:
        def select_for_update(self):
            return self

        def filter(self, **kwargs):
            stored.append(('inv_filter', kwargs))
            return self

        def first(self):
            return invoice

        def update(self, **kwargs):
            stored.append(('inv', kwargs))
            return 1

    inbox = SimpleNamespace(pk=uuid4(), processed_at=object() if inbox_processed else None)

    class _InboxQS:
        def select_for_update(self):
            return self

        def get_or_create(self, **kwargs):
            stored.append(('inbox_create', kwargs))
            return inbox, created

        def filter(self, **kwargs):
            return self

        def update(self, **kwargs):
            stored.append(('inbox', kwargs))
            return 1

    monkeypatch.setattr(Invoice, 'objects', _InvQS())
    monkeypatch.setattr(NeuranaWebhookInbox, 'objects', _InboxQS())
    monkeypatch.setattr(
        'platform.features.billing.commerce.invoice.application.fiscal_webhook.transaction.atomic',
        _AtomicNull(),
    )
    return stored


def _payload(invoice_id, status='issued'):
    return {
        'id': 'evt-1',
        'data': {
            'id': 'ne-1',
            'status': status,
            'number': 'NE-1',
            'metadata': {'wa_invoice_id': str(invoice_id)},
        },
    }


def test_apply_fiscal_webhook_persists_inbox(monkeypatch):
    invoice_id = uuid4()
    stored = _patch_webhook_models(
        monkeypatch, invoice=SimpleNamespace(pk=invoice_id, fiscal_status='pending'),
    )
    result = ApplyFiscalWebhookUseCase().execute(
        event_id='evt-1', event_type='invoice.issued', payload=_payload(invoice_id),
    )
    assert result['status'] == 'accepted'
    inv_update = next(kw for t, kw in stored if t == 'inv')
    assert inv_update['fiscal_status'] == 'issued'
    assert any(t == 'inbox' and kw['processed_at'] for t, kw in stored)


def test_apply_fiscal_webhook_duplicate_is_noop(monkeypatch):
    invoice_id = uuid4()
    stored = _patch_webhook_models(
        monkeypatch,
        invoice=SimpleNamespace(pk=invoice_id, fiscal_status='pending'),
        inbox_processed=True,
        created=False,
    )
    result = ApplyFiscalWebhookUseCase().execute(
        event_id='evt-1', event_type='invoice.issued', payload=_payload(invoice_id),
    )
    assert result == {'status': 'duplicate', 'http_status': 200, 'message': 'ECO_006'}
    assert not any(t == 'inv' for t, _ in stored)


def test_apply_fiscal_webhook_ignores_downgrade(monkeypatch):
    invoice_id = uuid4()
    stored = _patch_webhook_models(
        monkeypatch, invoice=SimpleNamespace(pk=invoice_id, fiscal_status='voided'),
    )
    result = ApplyFiscalWebhookUseCase().execute(
        event_id='evt-2', event_type='invoice.issued', payload=_payload(invoice_id),
    )
    assert result['status'] == 'ignored_downgrade'
    assert not any(t == 'inv' for t, _ in stored)
    assert next(kw for t, kw in stored if t == 'inbox')['processing_error'] == 'ignored_downgrade'


def test_void_persists_voiding_until_webhook(monkeypatch):
    invoice_id = uuid4()
    stored = {}
    invoice = SimpleNamespace(
        pk=invoice_id,
        fiscal_status='issued',
        external_id='ne-1',
        fiscal_payload={},
    )

    class _QS:
        def filter(self, **_kw):
            return self

        def first(self):
            return invoice

        def update(self, **kw):
            stored.update(kw)
            return 1

    monkeypatch.setattr(Invoice, 'objects', SimpleNamespace(filter=lambda **kw: _QS()))

    class Provider:
        def void(self, _request):
            return FiscalIssueResult(
                external_id='ne-1',
                fiscal_number='NE-1',
                fiscal_status='voiding',
                fiscal_payload={'status': 'voiding'},
            )

    result = VoidFiscalInvoiceUseCase(Provider()).execute(invoice_id)
    assert result == {'status': 'voiding', 'external_id': 'ne-1'}
    assert stored['fiscal_status'] == 'voiding'


def test_reconcile_updates_voiding_to_voided(monkeypatch):
    invoice_id = uuid4()
    invoice = SimpleNamespace(
        pk=invoice_id,
        fiscal_status='voiding',
        fiscal_number='NE-1',
        fiscal_payload={},
        external_id='ne-1',
    )
    stored = {}

    class _UpdateQS:
        def update(self, **kw):
            stored.update(kw)
            return 1

    monkeypatch.setattr(
        'platform.features.billing.commerce.invoice.application.fiscal_issue._invoices_needing_fiscal_poll',
        lambda *, limit: [invoice],
    )
    monkeypatch.setattr(Invoice.objects, 'filter', lambda **kw: _UpdateQS())

    class Provider:
        def get(self, _eid):
            return FiscalIssueResult(
                external_id='ne-1',
                fiscal_number='NE-1',
                fiscal_status='voided',
                fiscal_payload={'status': 'voided'},
            )

    result = ReconcileFiscalPendingUseCase(Provider()).execute()
    assert result['updated'] == 1
    assert stored['fiscal_status'] == 'voided'


def test_reconcile_does_not_downgrade_voiding_to_pending(monkeypatch):
    invoice = SimpleNamespace(
        pk=uuid4(),
        fiscal_status='voiding',
        fiscal_number='NE-1',
        fiscal_payload={},
        external_id='ne-1',
    )
    stored = {}

    class _UpdateQS:
        def update(self, **kw):
            stored.update(kw)
            return 1

    monkeypatch.setattr(
        'platform.features.billing.commerce.invoice.application.fiscal_issue._invoices_needing_fiscal_poll',
        lambda *, limit: [invoice],
    )
    monkeypatch.setattr(Invoice.objects, 'filter', lambda **kw: _UpdateQS())

    class Provider:
        def get(self, _eid):
            return FiscalIssueResult(
                external_id='ne-1',
                fiscal_number='NE-1',
                fiscal_status='pending',
                fiscal_payload={},
            )

    result = ReconcileFiscalPendingUseCase(Provider()).execute()
    assert result['updated'] == 0
    assert stored == {}
