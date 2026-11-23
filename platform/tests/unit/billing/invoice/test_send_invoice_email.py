"""Unit tests for SendInvoiceUseCase._send_email.

Focus: the invoice flow delegates email delivery to INotificationService
(the shared facade) instead of building a raw EmailMessage. We exercise the
delegation in isolation — no PDF render, no MinIO, no SMTP — by constructing
the use case with mocked collaborators and calling the (private) email step
directly with a ready-made blob.
"""
import base64
import uuid
from datetime import date
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

from core.errors import AppException, AppErrorCode

from platform.features.billing.commerce.invoice.application.send_invoice import (
    DEFAULT_INVOICE_EMAIL_CODE,
    SendInvoiceUseCase,
)
from platform.features.billing.commerce.invoice.domain.schemas import InvoiceSchema


def _invoice(**overrides) -> InvoiceSchema:
    defaults = dict(
        id=uuid.uuid4(),
        invoice_number='INV-2026-007',
        company_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        issue_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        total_amount=Decimal('49.99'),
        status='pending',
        notes='',
    )
    defaults.update(overrides)
    return InvoiceSchema(**defaults)


class TestSendInvoiceEmail(TestCase):

    def setUp(self):
        self.notification = MagicMock()
        self.notification.send_email.return_value = True
        self.use_case = SendInvoiceUseCase(
            invoice_repo=MagicMock(),
            storage=MagicMock(),
            notification=self.notification,
            directory=MagicMock(),
            template_loader=MagicMock(),
            render_resolver=MagicMock(),
            path_resolver=MagicMock(),
        )

    def _send(self, invoice=None, blob=b'%PDF-bytes', recipient='client@acme.com', context=None):
        invoice = invoice or _invoice()
        context = context if context is not None else {'invoice_number': invoice.invoice_number}
        self.use_case._send_email(
            invoice, blob, 'application/pdf', f'{invoice.invoice_number}.pdf', recipient, context,
        )
        return invoice

    # ── Delegation shape ─────────────────────────────────────────────────

    def test_delegates_to_notification_facade(self):
        self._send()
        self.notification.send_email.assert_called_once()

    def test_uses_invoice_email_template_and_recipient(self):
        self._send(recipient='billing@acme.com')
        _, kwargs = self.notification.send_email.call_args
        self.assertEqual(kwargs['template_code'], DEFAULT_INVOICE_EMAIL_CODE)
        self.assertEqual(kwargs['to'], ['billing@acme.com'])

    def test_forwards_the_email_context(self):
        ctx = {'user_name': 'Mario Pérez', 'total': 95.29, 'company_name': 'Acme'}
        self._send(context=ctx)
        _, kwargs = self.notification.send_email.call_args
        self.assertEqual(kwargs['context'], ctx)

    # ── Attachment ───────────────────────────────────────────────────────

    def test_pdf_attached_as_base64(self):
        self._send(blob=b'%PDF-1.7 hello')
        _, kwargs = self.notification.send_email.call_args
        att = kwargs['attachments'][0]
        self.assertEqual(att['filename'], 'INV-2026-007.pdf')
        self.assertEqual(att['mimetype'], 'application/pdf')
        # content must round-trip back to the original blob
        self.assertEqual(base64.b64decode(att['content']), b'%PDF-1.7 hello')

    # ── Failure propagation ──────────────────────────────────────────────

    def test_raises_when_facade_reports_failure(self):
        self.notification.send_email.return_value = False
        with self.assertRaises(AppException) as ctx:
            self._send()
        self.assertEqual(ctx.exception.code, AppErrorCode.INV_EMAIL_SEND_FAILED)

    def test_succeeds_silently_when_facade_reports_success(self):
        self.notification.send_email.return_value = True
        self._send()  # no raise
