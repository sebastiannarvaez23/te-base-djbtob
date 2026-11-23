"""Fiscal outbox: relay retry policy, breaker parking, dead letters and bell alerts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from platform.features.billing.commerce.fiscal_outbox.application.use_cases import (
    CheckFiscalSyncHealthUseCase,
    EnqueueFiscalIssueUseCase,
    EnqueueFiscalVoidUseCase,
    ReconcileFiscalOutboxUseCase,
    RelayFiscalOutboxUseCase,
)
from platform.features.billing.commerce.fiscal_outbox.domain.retry_policy import (
    RETRY_LADDER_SECONDS,
    next_delay_seconds,
)
from platform.features.billing.commerce.fiscal_outbox.domain.schemas import (
    FiscalBacklogSchema,
    FiscalDeadReason,
    FiscalOutboxEventSchema,
    FiscalOutboxKind,
    FiscalOutboxStatus,
)
from platform.features.billing.commerce.fiscal_outbox.infrastructure.alert_notifier import (
    FiscalSyncAlertNotifier,
)
from platform.features.billing.commerce.invoice.domain.fiscal import (
    FiscalRejectedError,
    FiscalTransientError,
)
from platform.features.billing.commerce.invoice.infrastructure.fiscal.neurana import (
    classify_remote_error,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


class MemoryRepo:
    def __init__(self):
        self.rows: dict = {}

    def _schema(self, row):
        return FiscalOutboxEventSchema(**row)

    def enqueue(self, data):
        for row in self.rows.values():
            if row['idempotency_key'] == data.idempotency_key:
                return self._schema(row), False
        row = {
            'id': uuid4(), 'kind': data.kind, 'invoice_id': data.invoice_id,
            'charge_id': data.charge_id, 'idempotency_key': data.idempotency_key,
            'reason': data.reason, 'trace_id': data.trace_id,
            'status': FiscalOutboxStatus.PENDING, 'attempts': 0,
            'next_attempt_at': NOW, 'created_at': NOW,
        }
        self.rows[row['id']] = row
        return self._schema(row), True

    def add(self, kind, *, invoice_id=None, created_at=NOW, attempts=0, status='pending'):
        row = {
            'id': uuid4(), 'kind': kind, 'invoice_id': invoice_id or uuid4(),
            'charge_id': uuid4(), 'idempotency_key': f'{kind}:{uuid4()}',
            'status': status, 'attempts': attempts,
            'next_attempt_at': NOW, 'created_at': created_at,
        }
        self.rows[row['id']] = row
        return row

    def claim_due(self, *, limit, lease_seconds):
        due = [r for r in self.rows.values() if r['status'] == 'pending' and r['next_attempt_at'] <= NOW]
        for r in due:
            r['status'] = 'processing'
        return [self._schema({**r, 'status': 'pending'}) for r in due[:limit]]

    def mark_done(self, event_id):
        self.rows[event_id]['status'] = 'done'

    def reschedule(self, event_id, *, next_attempt_at, attempts, error='', error_code=''):
        self.rows[event_id].update(
            status='pending', next_attempt_at=next_attempt_at, attempts=attempts,
            last_error=error, last_error_code=error_code,
        )

    def mark_dead(self, event_id, *, reason, error='', error_code=''):
        self.rows[event_id].update(status='dead', dead_reason=reason, last_error_code=error_code)

    def latest_for_invoice(self, invoice_id, kind):
        rows = [r for r in self.rows.values() if r['invoice_id'] == invoice_id and r['kind'] == kind.value]
        return self._schema(rows[-1]) if rows else None

    def has_event(self, invoice_id, kind):
        return self.latest_for_invoice(invoice_id, kind) is not None

    def stale_pending(self, *, created_before):
        rows = [r for r in self.rows.values()
                if r['status'] in ('pending', 'processing') and r['created_at'] < created_before]
        if not rows:
            return FiscalBacklogSchema()
        return FiscalBacklogSchema(count=len(rows), oldest_created_at=min(r['created_at'] for r in rows))

    def unalerted_dead(self, *, limit):
        return [self._schema(r) for r in self.rows.values()
                if r['status'] == 'dead' and not r.get('alerted')][:limit]

    def mark_alerted(self, event_ids):
        for eid in event_ids:
            self.rows[eid]['alerted'] = True


class FakeGateway:
    def __init__(self, *, issue=None, void=None):
        self._issue = issue or (lambda *a: 'issued')
        self._void = void or (lambda *a, **k: 'voided')
        self.rejected = []
        self.void_calls = []

    def issue(self, invoice_id, charge_id):
        return self._issue(invoice_id, charge_id)

    def void(self, invoice_id, **kwargs):
        self.void_calls.append(kwargs)
        return self._void(invoice_id, **kwargs)

    def mark_rejected(self, invoice_id, *, error_code):
        self.rejected.append((invoice_id, error_code))


def _raise(exc):
    def _fn(*a, **k):
        raise exc
    return _fn


def _relay(repo, gateway, **kwargs):
    return RelayFiscalOutboxUseCase(repo, gateway, clock=lambda: NOW, **kwargs)


def test_enqueue_is_idempotent_per_charge():
    repo = MemoryRepo()
    invoice_id, charge_id = uuid4(), uuid4()
    assert EnqueueFiscalIssueUseCase(repo).execute(invoice_id=invoice_id, charge_id=charge_id, trace_id='-')
    assert not EnqueueFiscalIssueUseCase(repo).execute(invoice_id=invoice_id, charge_id=charge_id)
    row = next(iter(repo.rows.values()))
    assert row['trace_id'] == ''
    assert EnqueueFiscalVoidUseCase(repo).execute(invoice_id=invoice_id, charge_id=charge_id)
    assert len(repo.rows) == 2


def test_relay_success_marks_done():
    repo = MemoryRepo()
    row = repo.add('issue')
    result = _relay(repo, FakeGateway()).execute()
    assert result.done == 1
    assert repo.rows[row['id']]['status'] == 'done'


def test_relay_transient_backs_off_on_ladder():
    repo = MemoryRepo()
    row = repo.add('issue')
    _relay(repo, FakeGateway(issue=_raise(FiscalTransientError('down', code='ECO_013')))).execute()
    stored = repo.rows[row['id']]
    assert stored['status'] == 'pending'
    assert stored['attempts'] == 1
    delay = (stored['next_attempt_at'] - NOW).total_seconds()
    assert RETRY_LADDER_SECONDS[0] * 0.8 <= delay <= RETRY_LADDER_SECONDS[0] * 1.2
    assert stored['last_error_code'] == 'ECO_013'


def test_relay_open_breaker_parks_batch_without_consuming_attempts():
    repo = MemoryRepo()
    first, second = repo.add('issue', attempts=2), repo.add('issue', attempts=0)
    calls = []

    def issue(*a):
        calls.append(a)
        raise FiscalTransientError('open', code='ECO_012', retry_after=45, circuit_open=True)

    result = _relay(repo, FakeGateway(issue=issue)).execute()
    assert result.circuit_open is True
    assert len(calls) == 1
    for row, attempts in ((first, 2), (second, 0)):
        stored = repo.rows[row['id']]
        assert stored['attempts'] == attempts
        assert stored['next_attempt_at'] == NOW + timedelta(seconds=45)


def test_relay_rejection_dead_letters_and_marks_invoice():
    repo = MemoryRepo()
    row = repo.add('issue')
    gateway = FakeGateway(issue=_raise(FiscalRejectedError('bad nit', code='FIN_010')))
    result = _relay(repo, gateway).execute()
    assert result.dead == 1
    assert repo.rows[row['id']]['dead_reason'] == FiscalDeadReason.REJECTED
    assert gateway.rejected == [(row['invoice_id'], 'FIN_010')]


def test_relay_expires_after_max_age():
    repo = MemoryRepo()
    row = repo.add('issue', created_at=NOW - timedelta(hours=73), attempts=20)
    _relay(repo, FakeGateway(issue=_raise(FiscalTransientError('down'))), max_age_hours=72).execute()
    assert repo.rows[row['id']]['status'] == 'dead'
    assert repo.rows[row['id']]['dead_reason'] == FiscalDeadReason.EXPIRED


def test_relay_missing_nit_is_retried_not_done():
    repo = MemoryRepo()
    row = repo.add('issue')
    _relay(repo, FakeGateway(issue=lambda *a: 'pending_missing_nit')).execute()
    assert repo.rows[row['id']]['status'] == 'pending'
    assert repo.rows[row['id']]['last_error_code'] == 'pending_missing_nit'


def test_voiding_outcome_is_done_not_retried():
    repo = MemoryRepo()
    row = repo.add('void')
    _relay(repo, FakeGateway(void=lambda *a, **k: 'voiding')).execute()
    assert repo.rows[row['id']]['status'] == 'done'


def test_void_waits_for_pending_issue_then_abandons_dead_issue():
    repo = MemoryRepo()
    invoice_id = uuid4()
    issue = repo.add('issue', invoice_id=invoice_id)
    issue['next_attempt_at'] = NOW + timedelta(hours=1)  # not due this tick
    void = repo.add('void', invoice_id=invoice_id)
    gateway = FakeGateway()

    result = _relay(repo, gateway).execute()
    assert result.deferred == 1
    assert gateway.void_calls == []
    assert repo.rows[void['id']]['attempts'] == 0

    issue['status'] = 'dead'
    repo.rows[void['id']]['next_attempt_at'] = NOW
    _relay(repo, gateway).execute()
    assert gateway.void_calls[0]['issue_abandoned'] is True
    assert repo.rows[void['id']]['status'] == 'done'


def test_retry_after_hint_extends_but_is_capped():
    assert next_delay_seconds(1, retry_after=600) == 600
    assert next_delay_seconds(1, retry_after=10_000) == 3600


class FakeNotifier:
    def __init__(self, fail=False):
        self.backlog = []
        self.dead = []
        self.fail = fail

    def breaker_changed(self, **kwargs):
        pass

    def backlog_stale(self, **kwargs):
        self.backlog.append(kwargs)

    def dead_letters(self, events):
        if self.fail:
            raise RuntimeError('bell down')
        self.dead.append(events)


def test_health_check_alerts_backlog_and_dead_once():
    repo = MemoryRepo()
    repo.add('issue', created_at=NOW - timedelta(minutes=40))
    dead = repo.add('issue', status='dead')
    notifier = FakeNotifier()
    use_case = CheckFiscalSyncHealthUseCase(repo, notifier, pending_minutes=15, clock=lambda: NOW)

    use_case.execute()
    assert notifier.backlog == [{'count': 1, 'oldest_minutes': 40}]
    assert [e.id for e in notifier.dead[0]] == [dead['id']]

    use_case.execute()
    assert len(notifier.dead) == 1


def test_health_check_keeps_dead_unalerted_when_bell_fails():
    repo = MemoryRepo()
    dead = repo.add('issue', status='dead')
    CheckFiscalSyncHealthUseCase(repo, FakeNotifier(fail=True), clock=lambda: NOW).execute()
    assert not repo.rows[dead['id']].get('alerted')


def test_reconcile_enqueues_only_missing_commands():
    repo = MemoryRepo()
    known, lost, refunded = uuid4(), uuid4(), uuid4()
    EnqueueFiscalIssueUseCase(repo).execute(invoice_id=known, charge_id=uuid4())

    class Lookup:
        def pending_without_document(self, *, limit):
            return [(known, uuid4()), (lost, uuid4()), (uuid4(), None)]

        def cancelled_with_live_document(self, *, limit):
            return [(refunded, uuid4())]

    result = ReconcileFiscalOutboxUseCase(repo, Lookup()).execute()
    assert result == {'issues_enqueued': 1, 'voids_enqueued': 1}


class MemoryCache:
    def __init__(self):
        self.data = {}

    def add(self, key, value, timeout=None):
        if key in self.data:
            return False
        self.data[key] = value
        return True

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        self.data.pop(key, None)


class CaptureDeliver:
    def __init__(self):
        self.payloads = []

    def execute(self, payload, user_ids):
        self.payloads.append(payload)
        return len(user_ids)


def _notifier():
    deliver = CaptureDeliver()
    return FiscalSyncAlertNotifier(
        deliver=deliver, recipients=lambda: [uuid4()], store=MemoryCache(),
    ), deliver


def test_bell_breaker_open_is_deduped_and_recovery_follows():
    notifier, deliver = _notifier()
    notifier.breaker_changed(previous='closed', new='open')
    notifier.breaker_changed(previous='half_open', new='open')
    assert len(deliver.payloads) == 1
    assert deliver.payloads[0].resource_route == '/admin/billing'

    notifier.breaker_changed(previous='half_open', new='closed')
    assert len(deliver.payloads) == 2
    assert deliver.payloads[1].level.value == 'SUCCESS'


def test_bell_recovery_without_prior_outage_is_silent():
    notifier, deliver = _notifier()
    notifier.breaker_changed(previous='half_open', new='closed')
    assert deliver.payloads == []


def _dead_event(reason=FiscalDeadReason.REJECTED):
    return FiscalOutboxEventSchema(
        id=uuid4(), kind=FiscalOutboxKind.ISSUE, invoice_id=uuid4(), idempotency_key='k',
        status=FiscalOutboxStatus.DEAD, next_attempt_at=NOW, created_at=NOW, dead_reason=reason,
    )


def test_bell_dead_letters_individual_then_digest():
    notifier, deliver = _notifier()
    events = [_dead_event() for _ in range(2)]
    notifier.dead_letters(events)
    assert [p.resource_id for p in deliver.payloads] == [e.invoice_id for e in events]

    notifier, deliver = _notifier()
    notifier.dead_letters([_dead_event() for _ in range(3)] + [_dead_event(FiscalDeadReason.EXPIRED)])
    assert len(deliver.payloads) == 1
    assert deliver.payloads[0].title.startswith('4 invoices')


def test_classify_remote_errors():
    from necore.ecosystem.exceptions import CircuitOpenError, RemoteEcosystemError

    opened = classify_remote_error(CircuitOpenError(retry_after=12))
    assert isinstance(opened, FiscalTransientError) and opened.circuit_open and opened.retry_after == 12
    assert isinstance(classify_remote_error(RemoteEcosystemError('X', http_status=503)), FiscalTransientError)
    assert isinstance(classify_remote_error(RemoteEcosystemError('ECO_001', http_status=401)), FiscalTransientError)
    rejected = classify_remote_error(RemoteEcosystemError('FIN_010', http_status=422))
    assert isinstance(rejected, FiscalRejectedError) and rejected.code == 'FIN_010'
    assert isinstance(classify_remote_error(OSError('boom')), FiscalTransientError)
