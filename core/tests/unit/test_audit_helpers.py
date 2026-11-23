"""core.audit: la persistencia de logs nunca rompe ni envenena la transacción."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from core import audit

pytestmark = pytest.mark.unit

FACTORY = 'client.features.logging.facade.factory.LogManagerFactory'
CONTEXT = 'client.features.logging.facade.context.LogContextBuilder'


@contextmanager
def _savepoint():
    yield


@pytest.fixture
def manager():
    manager = MagicMock()
    with patch('core.audit.transaction.atomic', side_effect=_savepoint) as atomic, \
            patch(FACTORY) as factory, patch(CONTEXT) as builder:
        factory.create.return_value = manager
        builder.from_request.return_value = 'ctx'
        manager.atomic = atomic
        yield manager


def test_audit_log_writes_inside_savepoint(manager):
    audit.audit_log(object(), 'item', 42, 'UPDATE', description='d', changes={'a': 1})
    ctx, data = manager.audit.call_args.args
    assert ctx == 'ctx'
    assert data.entity_id == '42'
    assert data.changes == {'a': 1}
    manager.atomic.assert_called_once()


def test_security_log_writes_event(manager):
    audit.security_log(object(), 'LOGIN_SUCCESS', resource='auth')
    assert manager.security.call_args.args[1].event_type == 'LOGIN_SUCCESS'


def test_warehouse_event_log_stringifies_reference(manager):
    audit.warehouse_event_log(object(), 'PICK', reference_type='order', reference_id=7)
    assert manager.warehouse_event.call_args.args[1].reference_id == '7'


def test_warehouse_event_log_keeps_missing_reference(manager):
    audit.warehouse_event_log(object(), 'PICK')
    data = manager.warehouse_event.call_args.args[1]
    assert data.reference_id is None
    assert data.payload is None
    assert data.warehouse_id is None


def test_warehouse_event_log_lists_related_records_once(manager):
    warehouse = '0199a6f4-2c1d-7c3e-9a51-6d1f0e2b8c47'
    audit.warehouse_event_log(
        object(), 'topology.access.assigned', payload={'locations': 2},
        warehouse_id=warehouse, refs=['b', 'a', None, 'b'],
    )
    data = manager.warehouse_event.call_args.args[1]
    assert data.payload == {'locations': 2, 'refs': ['a', 'b']}
    assert str(data.warehouse_id) == warehouse


def test_warehouse_event_log_does_not_mutate_the_payload(manager):
    payload = {'code': 'N1'}
    audit.warehouse_event_log(object(), 'topology.node.created', payload=payload, refs=['x'])
    assert payload == {'code': 'N1'}


@pytest.mark.parametrize('call, method', [
    (lambda: audit.audit_log(object(), 'item', 1, 'CREATE'), 'audit'),
    (lambda: audit.security_log(object(), 'LOGIN_FAILED'), 'security'),
    (lambda: audit.warehouse_event_log(object(), 'PICK'), 'warehouse_event'),
])
def test_failures_are_reported_without_raising(manager, call, method):
    getattr(manager, method).side_effect = RuntimeError('relation does not exist')
    with patch.object(audit.logger, 'warning') as warning:
        call()
    warning.assert_called_once()
    assert warning.call_args.kwargs['exc_info'] is True
